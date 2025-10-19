import { useState } from "react";
import { Button, Card, Select } from "flowbite-react";
import { useParser } from "./hooks/useParser";

function App() {
    const [query, setQuery] = useState("");
    const [parsedQuery, setParsedQuery] = useState(null);
    const [result, setResult] = useState(null);
    const [indexType, setIndexType] = useState("seqfile"); // 👈 nuevo estado
    const { parseQuery } = useParser();

    const handleExecute = async () => {
        if (!query.trim()) return;

        console.log(`➡️ Ejecutando con índice: ${indexType}`);
        const response = await parseQuery(query);
        setParsedQuery(response);
    };

    return (
        <div className="min-h-screen bg-gray-900 flex flex-col items-center p-6">
            <h1 className="text-2xl font-semibold mb-6 text-white">Mini DB</h1>

            <Card className="w-full max-w-4xl p-4">
                <textarea
                    className="w-full h-40 bg-gray-800 border border-gray-700 rounded-md p-2 font-mono text-sm text-white focus:ring-2 focus:ring-blue-400 outline-none"
                    placeholder="Escribe una consulta SQL aquí..."
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                />

                <div className="flex justify-between items-center mt-4">
                    <div className="flex items-center gap-2">
                        <label htmlFor="indexType" className="text-white text-sm">
                            Tipo de índice:
                        </label>
                        <Select
                            id="indexType"
                            value={indexType}
                            onChange={(e) => setIndexType(e.target.value)}
                            className="bg-gray-800 text-white border-gray-700 text-sm"
                        >
                            <option value="-">-</option>
                            <option value="bplustree">bplustree</option>
                            <option value="seqfile">seqfile</option>
                            <option value="exthashing">exthashing</option>
                            <option value="isam">isam</option>
                        </Select>
                    </div>

                    <Button color="blue" onClick={handleExecute}>
                        Ejecutar
                    </Button>
                </div>

                <div className="mt-6">
                    <h2 className="text-lg font-medium mb-2 text-white">Database Result:</h2>
                    <div className="bg-gray-100 border border-gray-300 rounded-md p-4 text-sm font-mono min-h-[100px] overflow-auto">
                        {result ? (
                            <pre>{JSON.stringify(result, null, 2)}</pre>
                        ) : (
                            "Sin resultados aún..."
                        )}
                    </div>
                </div>

                {parsedQuery && (
                    <div className="mt-6">
                        <h2 className="text-lg font-medium mb-2 text-white">Parsed Query (Debug):</h2>
                        <div className="bg-gray-800 border border-gray-700 rounded-md p-4 text-sm font-mono text-green-300 overflow-auto">
                            <pre>{JSON.stringify(parsedQuery, null, 2)}</pre>
                        </div>
                    </div>
                )}
            </Card>
        </div>
    );
}

export default App;
