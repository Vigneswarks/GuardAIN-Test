const fs = require('node:fs');
const vm = require('node:vm');
let count = 0;
for (const file of ['admin_portal/index.html', 'pwa/index.html']) {
  for (const match of fs.readFileSync(file, 'utf8').matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)) {
    if (match[1].trim()) { new vm.Script(match[1], {filename: file}); count++; }
  }
}
if (count < 3) throw new Error('Expected portal configuration, application and PWA scripts');
console.log(`${count} inline scripts parsed successfully`);
