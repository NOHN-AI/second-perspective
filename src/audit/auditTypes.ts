export interface ResponsibilityAccount {
  organization: string;
  role: string;
  stage: string;
  nonce: string;
}

export interface Assumption {
  id: string;
  text: string;
}

export interface Branch {
  if: string;
  then: string;
  response: string;
}

export interface ImdaScores {
  interpretability: number;
  robustness: number;
  accountability: number;
  inclusiveness: number;
  overall: number;
}

export interface AuditReport {
  disclaimer?: string;
  responsibility_account?: ResponsibilityAccount;
  decision?: { D: string };
  assumptions?: Assumption[];
  branch_logic?: Branch[];
  imda_scores?: ImdaScores;
  overall_score?: number;
  verdict?: boolean;
  source?: string;
  error?: string;
}

export interface DecisionContext {
  decision: string;
  context?: string;
  metadata?: { source?: string; language?: string; [k: string]: unknown };
}
