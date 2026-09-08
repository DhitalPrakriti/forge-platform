import { z } from "zod";
export const identitySchema = z.object({
  name: z.string().trim().min(1, "Enter a name.").max(200),
  slug: z
    .string()
    .max(100)
    .regex(
      /^[a-z0-9]+(?:-[a-z0-9]+)*$/,
      "Use lowercase letters, numbers, and single hyphens.",
    ),
});
export const agentSchema = identitySchema.extend({
  description: z.string().max(10000),
});
export const organizationIdSchema = z.object({
  id: z.string().uuid("Enter a valid organization UUID."),
});
export const versionSchema = z.object({
  tool_version_ids: z.array(z.string().uuid()).max(100),
  version: z.string().trim().min(1, "Give this version a label.").max(100),
  goal: z.string().trim().min(1, "Describe the agent’s goal.").max(10000),
  instructions: z
    .string()
    .trim()
    .min(1, "Add instructions for the model.")
    .max(100000),
  primary_model: z
    .string()
    .trim()
    .min(1, "Enter the model identifier.")
    .max(200),
  max_steps: z.number().int().min(1).max(1000),
  max_runtime_seconds: z.number().int().min(1).max(86400),
  max_cost_per_run_usd: z
    .string()
    .regex(/^\d{1,6}(\.\d{1,6})?$/, "Use up to 6 decimal places.")
    .refine((v) => Number(v) > 0, "Budget must be positive."),
});
export const runSchema = z.object({
  message: z.string().trim().min(1, "Enter a message.").max(20000),
});
export type IdentityValues = z.infer<typeof identitySchema>;
export type AgentValues = z.infer<typeof agentSchema>;
export type VersionValues = z.infer<typeof versionSchema>;
