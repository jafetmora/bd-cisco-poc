# services/ai_engine/app/config/ea_catalog.py

EA_CATALOG = [
    {
        "ea_id": "EA-MERAKI",
        "name": "Meraki EA",
        "threshold_usd": 150_000,
        "expected_savings_pct": 0.18,
        "scope": {"meraki"},
        "notes": "Descontos agregados Meraki, flexibilidade de expansão sem renegociação."
    },
    {
        "ea_id": "EA-ENT-NET",
        "name": "Enterprise Networking EA",
        "threshold_usd": 250_000,
        "expected_savings_pct": 0.15,
        "scope": {"meraki", "enterprise_networking"},
        "notes": "Agrupa redes (Meraki + Catalyst) com gestão e desconto unificados."
    },
    {
        "ea_id": "EA-SECURITY",
        "name": "Security EA",
        "threshold_usd": 200_000,
        "expected_savings_pct": 0.16,
        "scope": {"security", "meraki"},
        "notes": "Benefícios para suites de segurança e MX em contratos centralizados."
    },
]
