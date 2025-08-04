import { useState } from "react";

interface Scenario {
  id: string;
  label: string;
  price: number;
}

function App() {
  const [input, setInput] = useState("");
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [loading, setLoading] = useState(false);

  async function send() {
    if (!input) return;
    setLoading(true);
    const res = await fetch("http://localhost:8000/quote", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: input }),
    });
    const data = await res.json();
    setScenarios(data.scenarios);
    setLoading(false);
  }

  return (
    <main className="p-8 max-w-xl mx-auto">
      <h1 className="text-2xl font-semibold mb-4">Quote Assistant PoC</h1>
      <div className="flex gap-2">
        <input
          className="flex-1 border p-2 rounded"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type your quote request…"
        />
        <button
          className="bg-blue-600 text-white px-4 rounded"
          onClick={send}
          disabled={loading}
        >
          {loading ? "..." : "Send"}
        </button>
      </div>

      <section className="mt-6 grid gap-4">
        {scenarios.map((s) => (
          <div
            key={s.id}
            className="border rounded p-4 shadow-sm flex justify-between"
          >
            <span>{s.label}</span>
            <span>${s.price.toLocaleString()}</span>
          </div>
        ))}
      </section>
    </main>
  );
}

export default App;
