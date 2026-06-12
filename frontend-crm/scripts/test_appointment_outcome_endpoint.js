import fs from "node:fs";
import path from "node:path";

const filePath = path.join(process.cwd(), "src", "services", "api.ts");
const contents = fs.readFileSync(filePath, "utf8");

if (!contents.includes("setOutcome")) {
  throw new Error("api.appointments.setOutcome is missing");
}

console.log("ok");
