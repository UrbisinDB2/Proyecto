import { useState } from "react";
import { Button, Card } from "flowbite-react";

function App() {
    const [query, setQuery] = useState("");
    const [parsedQuery, setParsedQuery] = useState({});
    const [result, setResult] = useState({});

    const handleExecute = async () => {

    };

    return (
        <div className="min-h-screen bg-gray-900 flex flex-col items-center p-6">
            <h1 className="text-2xl font-semibold mb-6 text-white">Mini DB</h1>

            <Card className="w-full max-w-4xl p-4">
                <textarea
                    className="w-full h-40 border border-gray-300 rounded-md p-2 font-mono text-sm focus:ring-2 focus:ring-blue-400 outline-none text-white"
                    placeholder="Escribe una consulta SQL aquí..."
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                />

                <div className="flex justify-end mt-4">
                    <Button color="blue" onClick={handleExecute}>
                        Ejecutar
                    </Button>
                </div>

                <div className="mt-6">
                    <h2 className="text-lg font-medium mb-2 text-white">Resultado:</h2>
                    <div className="bg-white border border-gray-300 rounded-md p-4 text-sm font-mono min-h-[100px]">
                        {result || "Sin resultados aún..."}
                    </div>
                </div>
            </Card>
        </div>
    );
}

export default App
