"""
eval_dataset.py
Hand-labeled question/ground-truth pairs used to evaluate retrieval and
generation quality with RAGAS. Covers both document types deliberately:
- Synthetic invoices/contracts: precise, verifiable factual answers
- Real 10-Ks: harder, longer-context questions

Ground truths were verified by manually checking the source documents.
"""

EVAL_QUESTIONS = [
    {
        "question": "What is the invoice number for the Acme Supplies invoice dated 2026-06-01?",
        "ground_truth": "INV-1001",
    },
    {
        "question": "What is the penalty clause in the Acme Supplies vendor agreement?",
        "ground_truth": "2% penalty per week on overdue payments beyond 30 days",
    },
    {
        "question": "What is the total contract value in the BlueWave Logistics vendor agreement?",
        "ground_truth": "300,000 INR",
    },
    {
        "question": "What are the payment terms in the BlueWave Logistics vendor agreement?",
        "ground_truth": "Net 45 days from invoice date",
    },
    {
        "question": "What is the total amount due on invoice INV-2002 from BlueWave Logistics?",
        "ground_truth": "55,460 (subtotal 47,000 + 18% tax 8,460)",
    },
    {
        "question": "What currency is used on the Global Tech Supplies Inc invoice?",
        "ground_truth": "USD",
    },
    {
        "question": "What was Microsoft's fiscal year end date for their most recent 10-K filing?",
        "ground_truth": "June 30, 2026",
    },
    {
        "question": "What are the main risk factors Microsoft discusses related to competition?",
        "ground_truth": (
            "Microsoft's 10-K discusses risks from intense competition across its "
            "product and service categories, competitors with greater resources or "
            "focus, and rapidly evolving technology and business models."
        ),
    },
    {
        "question": "What fiscal year end date does Walmart use for its annual reporting?",
        "ground_truth": "Late January (fiscal year ends January 31)",
    },
    {
        "question": "What kind of business does JPMorgan primarily disclose risk around in its 10-K?",
        "ground_truth": (
            "JPMorgan's 10-K discusses credit risk, market risk, and risk related to "
            "its banking, investment banking, and asset management operations."
        ),
    },
]
