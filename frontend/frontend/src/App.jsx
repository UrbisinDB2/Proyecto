import { useState } from "react";
import { Button, Card, Select, Table, TableBody, TableCell, TableHead, TableHeadCell, TableRow } from "flowbite-react";
import { useParser } from "./hooks/useParser";
import { useDatabase } from "./hooks/useDatabase";

function App() {
    const [query, setQuery] = useState("");
    const [parsedQuery, setParsedQuery] = useState(null);
    const [result, setResult] = useState(null);
    const [indexType, setIndexType] = useState("seqfile");
    const { parseQuery } = useParser();
    const { executeOperation } = useDatabase();

    const handleExecute = async () => {
        if (!query.trim()) return;

        const parsedResponse = await parseQuery(query);
        setParsedQuery(parsedResponse);

        if (parsedResponse && parsedResponse.op) {
            const dbResponse = await executeOperation(parsedResponse, indexType);
            setResult(dbResponse);
        }
    };

    return (
        <div className="min-h-screen bg-gray-900 flex flex-col items-center p-6">
            <h1 className="text-2xl font-semibold mb-6 text-white">Mini DB</h1>

            <Card className="w-full max-w-6xl p-4">
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

                {/* JSON del parser */}
                {parsedQuery && (
                    <div className="mt-6">
                        <h2 className="text-lg font-medium mb-2 text-white">Parsed Query (Debug):</h2>
                        <div className="bg-gray-800 border border-gray-700 rounded-md p-4 text-sm font-mono text-green-300 overflow-auto">
                            <pre>{JSON.stringify(parsedQuery, null, 2)}</pre>
                        </div>
                    </div>
                )}

                {/* JSON del resultado */}
                {result && (
                    <div className="mt-6">
                        <h2 className="text-lg font-medium mb-2 text-white">Database Result:</h2>
                        <div className="bg-gray-100 border border-gray-300 rounded-md p-4 text-sm font-mono overflow-auto">
                            <pre>{JSON.stringify(result, null, 2)}</pre>
                        </div>
                    </div>
                )}

                {/* --- Tabla de resultados del SELECT --- */}
                {result && Array.isArray(result.result) && result.result.length > 0 && (
                    <div className="mt-10">
                        <h2 className="text-lg font-medium mb-3 text-white">Resultados de la consulta:</h2>
                        <div className="overflow-x-auto rounded-md border border-gray-700">
                            <Table striped hoverable>
                                <TableHead>
                                    {Object.keys(result.result[0]).map((key) => (
                                        <TableHeadCell key={key} className="capitalize">
                                            {key}
                                        </TableHeadCell>
                                    ))}
                                </TableHead>
                                <TableBody className="divide-y">
                                    {result.result.map((row, i) => (
                                        <TableRow key={i} className="bg-gray-800 text-white">
                                            {Object.values(row).map((value, j) => (
                                                <TableCell key={j} className="whitespace-nowrap">
                                                    {String(value)}
                                                </TableCell>
                                            ))}
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </div>
                        <p className="text-sm text-gray-400 mt-3">
                            Mostrando {result.count} resultado{result.count !== 1 && "s"} (engine:{" "}
                            <span className="font-mono">{result.engine}</span>)
                        </p>
                    </div>
                )}
            </Card>
        </div>
    );
}

export default App;
