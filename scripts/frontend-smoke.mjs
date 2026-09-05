const baseUrl = process.env.FRONTEND_URL || "http://127.0.0.1:3100";
const response = await fetch(`${baseUrl}/whiteboard`);
if (response.status !== 200) throw new Error(`frontend returned ${response.status}`);
const html = await response.text();
if (!html.includes("Whiteboard editor")) throw new Error("whiteboard editor landmark missing");
console.log(JSON.stringify({ status: "ok", route: "/whiteboard", bytes: html.length }));
