// Run the node:test suites in one process, including restricted Windows environments.
const fs = require('node:fs');
const path = require('node:path');
for (const file of fs.readdirSync(__dirname).filter(file => file.endsWith('.test.cjs')).sort()) {
  require(path.join(__dirname, file));
}
