// json_handler.js
let pricing;

async function loadPricingData() {
  try {
    if (typeof window !== "undefined") {
      // ✅ Browser environment
      const response = await fetch("../pricing/pricing.json");
      pricing = await response.json();
    } else {
      // ✅ Node environment (FastAPI subprocess)
      const { promises: fs } = await import("fs");
      const path = await import("path");
      const { fileURLToPath } = await import("url");

      const __filename = fileURLToPath(import.meta.url);
      const __dirname = path.dirname(__filename);

      const filePath = path.join(__dirname, "../../pricing/pricing.json");
      const data = await fs.readFile(filePath, "utf-8");
      pricing = JSON.parse(data);
    }

    return pricing;
  } catch (error) {
    console.error("Error loading pricing data:", error);
  }
}

export { loadPricingData };
