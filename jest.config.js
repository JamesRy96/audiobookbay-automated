// File: jest.config.js
module.exports = {
    setupFilesAfterEnv: ["<rootDir>/jest.setup.js"],
    testEnvironment: "jsdom",
    modulePathIgnorePatterns: ["<rootDir>/.agents/"],
    // Added vendor_integration.test.js and status.test.js
    testMatch: [
        "<rootDir>/tests/js/search.test.js",
        "<rootDir>/tests/js/actions.test.js",
        "<rootDir>/tests/js/vendor_integration.test.js",
        "<rootDir>/tests/js/status.test.js",
        "<rootDir>/tests/js/diagnostics.test.js",
    ],
};
