import axios from "axios";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const DATABASE_URL = `${BASE_URL}/database`;

export const useDatabase = () => {
    const executeOperation = async (parsedQuery, indexType) => {
        if (!parsedQuery || typeof parsedQuery !== "object") {
            console.error("❌ No se proporcionó una query válida al hook useDatabase");
            return { error: "Invalid query object" };
        }

        if (!indexType || typeof indexType !== "string") {
            console.error("⚠️ No se proporcionó un tipo de índice válido");
            return { error: "Invalid index type" };
        }

        try {
            if (parsedQuery["op"] === 1 || parsedQuery["op"] === 2 ||  parsedQuery["op"] === 4) {
                parsedQuery["idx"] = indexType;
            }
            const response = await axios.post(DATABASE_URL, parsedQuery);
            console.log("✅ Respuesta de /database:", response.data);
            return response.data;
        } catch (error) {
            console.error("⚠️ Error al ejecutar en /database:", error);
            return { error: error.response?.data || error.message };
        }
    };

    return { executeOperation };
};
