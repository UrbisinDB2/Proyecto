import axios from "axios";

const PARSER_URL = "http://localhost:8000/parser"; // ⚠️ cambia si usas otro puerto

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
