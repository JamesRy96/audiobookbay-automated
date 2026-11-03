# File: audiobook_automated/clients/manager.py
"""Manager for handling Torrent Client plugins."""

import importlib
import inspect
import logging
import re

from flask import Flask

from .base import TorrentClientPlugin, TorrentStatus

logger = logging.getLogger(__name__)


class TorrentManager:
    """Manages the lifecycle and interaction with configured download clients."""

    def __init__(self) -> None:
        """Initialize the manager."""
        self._client: TorrentClientPlugin | None = None
        self.clients: dict[str, TorrentClientPlugin] = {}
        self._app: Flask | None = None

    @property
    def client(self) -> TorrentClientPlugin | None:
        """Return the active or primary download client plugin."""
        return self._client

    @client.setter
    def client(self, value: TorrentClientPlugin | None) -> None:
        """Set the active or primary download client plugin."""
        self._client = value  # pragma: no cover

    @client.deleter
    def client(self) -> None:
        """Deleter for client."""
        self._client = None  # pragma: no cover

    @property
    def client_type(self) -> str:
        """Return the name of the loaded client plugin."""
        if self._client:
            return self._client.__class__.__name__
        return "None"

    def init_app(self, app: Flask) -> None:
        """Initialize the manager with the Flask application.

        Args:
            app: The Flask application instance.
        """
        self._app = app
        self._load_clients(app)
        app.teardown_appcontext(self.teardown_request)

    def _instantiate_client(self, app: Flask, client_name: str) -> TorrentClientPlugin | None:
        """Instantiate a client plugin by name with app configuration.

        Args:
            app: The Flask application instance.
            client_name: The client module name.

        Returns:
            TorrentClientPlugin | None: The loaded client instance or None on error.
        """
        # Validate client_name to prevent arbitrary code execution
        # Only allow alphanumeric characters, underscores, and hyphens
        if not re.match(r"^[a-zA-Z0-9_\-]+$", client_name):
            logger.error("Security: Invalid DL_CLIENT name '%s'. No client loaded.", client_name)
            return None

        module_name = f"audiobook_automated.clients.{client_name}"
        class_name = f"{client_name.capitalize()}Client"

        try:
            logger.info("Plugin: Loading download client '%s'...", client_name)
            module = importlib.import_module(module_name)

            # Find the client class in the module
            client_class = None
            for _, obj in inspect.getmembers(module, inspect.isclass):
                # Ensure it is a class before issubclass to satisfy MyPy/Pyright strict checks
                # pyright: ignore[reportUnnecessaryIsInstance]
                if issubclass(obj, TorrentClientPlugin) and obj is not TorrentClientPlugin:
                    client_class = obj
                    break

            if not client_class:
                client_class = getattr(module, class_name, None)

            if not client_class:
                raise ImportError(f"No valid client plugin class found in {module_name}")

            # Instantiate the client plugin
            # Extract configuration from app.config to pass explicitly
            settings = app.config.get("CLIENT_CONNECTIONS", {}).get(client_name, {})
            client_cls: type[TorrentClientPlugin] = client_class
            instance = client_cls(
                host=settings.get("HOST") or "localhost",
                port=int(settings.get("PORT") or getattr(client_class, "DEFAULT_PORT", 8080)),
                username=settings.get("USERNAME"),
                password=settings.get("PASSWORD"),
                scheme=settings.get("SCHEME") or "http",
                timeout=int(settings.get("TIMEOUT") or app.config.get("CLIENT_TIMEOUT", 5)),
                api_key=settings.get("API_KEY"),
                token=settings.get("TOKEN"),
                folder_id=settings.get("FOLDER_ID", "0"),
                dl_url=settings.get("URL"),
            )
            logger.info("Plugin: Successfully loaded '%s'.", client_name)
            return instance

        except (ImportError, AttributeError, TypeError) as e:
            logger.exception("Plugin: Failed to load client '%s'. Error: %s", client_name, e)
            return None

    def _load_clients(self, app: Flask) -> None:
        """Dynamically load the configured torrent download clients.

        The first name in DL_CLIENT is the default; additional comma-separated names are selectable.

        Args:
            app: The Flask application instance containing configuration.
        """
        self.clients.clear()
        configured = app.config.get("DL_CLIENT") or ""
        client_names = list(dict.fromkeys(name.strip().lower() for name in configured.split(",") if name.strip()))
        primary_client = client_names[0] if client_names else ""

        for name in client_names:
            instance = self._instantiate_client(app, name)
            if instance:
                self.clients[name.lower()] = instance

        # Set default primary client
        if primary_client.lower() in self.clients:
            self._client = self.clients[primary_client.lower()]
        elif self.clients:
            self._client = next(iter(self.clients.values()))
        else:
            self._client = None

    def get_client(self, client_name: str | None = None) -> TorrentClientPlugin | None:
        """Get a specific download client by name, or the default primary client."""
        if client_name:
            return self.clients.get(client_name.lower())
        return self._client

    def list_clients(self) -> list[str]:
        """Return list of configured client identifiers."""
        return list(self.clients.keys())

    def verify_credentials(self, client_name: str | None = None) -> bool:
        """Verify that the target or primary download client can connect."""
        target = self.get_client(client_name)
        if not target:
            return False
        name = client_name or next(
            (name for name, instance in self.clients.items() if instance is target), self.client_type
        )
        logger.info("Checking Download Client '%s'. Please wait for the connection result.", name)
        connected = target.verify_credentials()
        if not connected:
            logger.warning(
                "Cannot connect to Download Client '%s'. Check that it is running, then check %s_HOST, %s_PORT "
                "and its login settings. If this app and client share Gluetun's network, use %s_HOST=127.0.0.1. "
                "For a separate server, use its reachable address.",
                name,
                name.upper(),
                name.upper(),
                name.upper(),
            )
        return connected

    @staticmethod
    def _ensure_connected(client: TorrentClientPlugin) -> None:
        """Open this request thread's transport once before using a client operation."""
        if client.client is None and client.session is None:
            logger.info("Connecting to Download Client %s...", type(client).__name__.removesuffix("Client"))
            client.connect()

    def add_magnet(self, magnet_link: str, save_path: str | None, client_name: str | None = None) -> None:
        """Add a magnet link to the client.

        Args:
            magnet_link: The magnet URI.
            save_path: The filesystem path to save the download.
            client_name: Optional target client identifier.
        """
        target = self.get_client(client_name)
        if not target:
            raise ConnectionError("No Download Client is configured.")

        category = "abb-automated"
        if self._app:
            category = self._app.config.get("DL_CATEGORY", "abb-automated")

        self._ensure_connected(target)
        target.add_magnet(magnet_link, save_path, category)

    def get_status(self, client_name: str | None = None) -> list[TorrentStatus]:
        """Get the status of torrents in the configured category across all or targeted clients.

        Args:
            client_name: Optional client identifier to restrict query to.

        Returns:
            A list of TorrentStatus objects with client field populated.
        """
        category = "abb-automated"
        if self._app:
            category = self._app.config.get("DL_CATEGORY", "abb-automated")

        if client_name and client_name.lower() in self.clients:
            client_instance = self.clients[client_name.lower()]
            self._ensure_connected(client_instance)
            statuses = client_instance.get_status(category)
            for s in statuses:
                s.client = client_name.lower()
            return statuses

        if client_name:
            raise ConnectionError("The selected Download Client is not configured.")

        # Multi-client status aggregation
        if len(self.clients) > 1:
            aggregated: list[TorrentStatus] = []
            reached_clients = 0
            for name, client_instance in self.clients.items():
                try:
                    self._ensure_connected(client_instance)
                    statuses = client_instance.get_status(category)
                    reached_clients += 1
                    for s in statuses:
                        s.client = name
                    aggregated.extend(statuses)
                except Exception as e:
                    logger.warning(f"Manager: Failed to get status for client '{name}': {e}")
            if not reached_clients:
                raise ConnectionError(
                    "No Download Clients could be reached. Check their host, port and login settings. "
                    "If they share Gluetun with this app, set their HOST settings to 127.0.0.1."
                )
            return aggregated

        if not self._client:
            return []

        self._ensure_connected(self._client)
        statuses = self._client.get_status(category)
        default_name = next(iter(self.clients.keys()), "").lower()
        if not default_name:
            default_name = self.client_type.lower().replace("client", "").replace("plugin", "")

        for s in statuses:
            s.client = default_name
        return statuses

    def remove_torrent(self, torrent_id: str, delete_data: bool = False, client_name: str | None = None) -> bool:
        """Remove a torrent from the client.

        Args:
            torrent_id: The ID (info hash).
            delete_data: Whether to delete the downloaded files.
            client_name: Optional specific client to remove from.

        Returns:
            True if successful, False otherwise.
        """
        target = self.get_client(client_name)
        if target:
            try:
                self._ensure_connected(target)
                target.remove_torrent(torrent_id)
                return True
            except Exception as e:
                logger.error(f"Manager: Failed to remove torrent {torrent_id}: {e}")
                return False

        if client_name:
            return False

        # If no client specified and multiple exist, attempt removal across clients
        for name, client_instance in self.clients.items():
            try:
                self._ensure_connected(client_instance)
                client_instance.remove_torrent(torrent_id)
                return True
            except Exception as e:
                logger.debug(f"Manager: Client '{name}' could not remove torrent {torrent_id}: {e}")

        return False

    def close(self) -> None:
        """Close any open connections held by all download clients."""
        for client_instance in self.clients.values():
            client_instance.close()
        if self._client and not self.clients:
            self._client.close()

    def teardown_request(self, exception: BaseException | None = None) -> None:
        """Cleanup request-scoped resources across download clients."""
        for client_instance in self.clients.values():
            client_instance.teardown()
        if self._client and not self.clients:
            self._client.teardown()
