import type { ToolName } from "./api/types";
// Explicit test commands for FakeAdapter; these are not natural-language model decisions.
export const DEMO_TOOLS: {
  name: ToolName;
  label: string;
  description: string;
  message: string;
}[] = [
  {
    name: "issue_refund",
    label: "Simulated refund",
    description:
      "Record a local refund. USD 50 allows, 425 needs approval, 700 denies.",
    message:
      '/tool issue_refund {"customer_id":"cust_001","amount_usd":"425.00"}',
  },
  {
    name: "lookup_customer",
    label: "Customer lookup",
    description: "Read a synthetic customer profile.",
    message: '/tool lookup_customer {"customer_id":"cust_001"}',
  },
  {
    name: "lookup_transactions",
    label: "Transactions lookup",
    description: "Read synthetic customer transactions.",
    message: '/tool lookup_transactions {"customer_id":"cust_001"}',
  },
  {
    name: "create_ticket",
    label: "Create demo ticket",
    description: "Save a ticket in this workspace’s local database.",
    message:
      '/tool create_ticket {"customer_id":"cust_001","title":"Plan question","details":"Please explain my plan."}',
  },
];
