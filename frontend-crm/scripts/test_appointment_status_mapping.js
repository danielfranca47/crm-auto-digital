import fs from "node:fs";
import path from "node:path";

const filePath = path.join(
  process.cwd(),
  "src",
  "hooks",
  "useAppointments.ts"
);
const contents = fs.readFileSync(filePath, "utf8");

if (!contents.includes('rawStatus === "scheduled" ? "pending" : rawStatus')) {
  throw new Error("normalizeAppointment should map scheduled -> pending");
}

console.log("ok");
