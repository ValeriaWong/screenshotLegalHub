import fs from "node:fs";
import path from "node:path";
const errors = [];
function walk(dir) {
  for (const name of fs.readdirSync(dir)) {
    const file = path.join(dir, name);
    if (fs.statSync(file).isDirectory()) walk(file);
    else if (/\.(ts|tsx|css)$/.test(file)) {
      const source = fs.readFileSync(file, "utf8");
      if (/#[\da-f]{3,8}\b|\brgba?\(/i.test(source))
        errors.push(file + ": hard-coded feature color");
      if (
        /from\s+['"](?:@mui|antd|@radix-ui|@chakra-ui|lucide|framer-motion)/.test(
          source,
        )
      )
        errors.push(file + ": direct UI/icon/motion vendor dependency");
    }
  }
}
walk("src/features");
if (errors.length) {
  console.error(errors.join("\n"));
  process.exit(1);
}
console.log("UI architecture guards passed");
