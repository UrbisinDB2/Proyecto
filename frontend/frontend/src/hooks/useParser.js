import axios from "axios";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const PARSER_URL = `${BASE_URL}/parser`;

export const useParser = () => {
    const parseQuery = async (text) => {
        try {
            const response = await axios.post(PARSER_URL, { "text": text });
            return response.data;
        } catch (error) {
            console.error("Error al parsear:", error);
            return { error: error.message };
        }
    };

    return { parseQuery };
};
