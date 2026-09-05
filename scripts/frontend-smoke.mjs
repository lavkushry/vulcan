const baseUrl = process.env.FRONTEND_URL || "http://127.0.0.1:3100";
let response;
let lastError;
for (let attempt = 0; attempt < 30; attempt += 1) {
  try { response = await fetch(`${baseUrl}/whiteboard`); if (response.status === 200) break; }
  catch (error) { lastError = error; }
  await new Promise((resolve) => setTimeout(resolve, 500));
}
if (!response) throw lastError || new Error("frontend did not start");
if (response.status !== 200) throw new Error(`frontend returned ${response.status}`);
const html = await response.text();
if (!html.includes("Whiteboard editor")) throw new Error("whiteboard editor landmark missing");
console.log(JSON.stringify({ status: "ok", route: "/whiteboard", bytes: html.length }));
