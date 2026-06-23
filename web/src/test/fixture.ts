import type { Brief } from '../types'

export const BRIEF_FIXTURE: Brief = {
  topic: 'mRNA vaccine effectiveness',
  generated_at: '2024-01-15T10:00:00Z',
  sources: [
    {
      id: 's1',
      url: 'https://example.com/study-a',
      title: 'Study A: High Efficacy',
      status: 'ok',
      fetch_method: 'direct',
      error: null,
    },
    {
      id: 's2',
      url: 'https://example.com/study-b',
      title: 'Study B: Moderate Efficacy',
      status: 'ok',
      fetch_method: 'direct',
      error: null,
    },
    {
      id: 's3',
      url: 'https://example.com/paywall',
      title: 'Paywalled Journal',
      status: 'paywalled',
      fetch_method: null,
      error: 'Access denied',
    },
  ],
  claim_clusters: [
    {
      id: 'c1',
      statement: 'mRNA vaccines reduce hospitalisation risk significantly.',
      classification: 'consensus',
      members: [
        {
          source_id: 's1',
          stance: 'supports',
          claim_text: 'Vaccine reduces hospitalisations by 90%.',
          supporting_quote: 'We observed a 90% reduction in hospitalisation rates.',
          confidence: 'high',
        },
      ],
    },
    {
      id: 'c2',
      statement: 'Vaccine effectiveness wanes after 6 months.',
      classification: 'contested',
      members: [
        {
          source_id: 's1',
          stance: 'supports',
          claim_text: 'Efficacy drops to 40% after 6 months.',
          supporting_quote: 'Six-month follow-up shows declining efficacy.',
          confidence: 'medium',
        },
        {
          source_id: 's2',
          stance: 'contradicts',
          claim_text: 'No significant waning observed at 6 months.',
          supporting_quote: 'Protection remained robust at 6 months post-vaccination.',
          confidence: 'medium',
        },
      ],
    },
    {
      id: 'c3',
      statement: 'mRNA technology may trigger autoimmune responses in rare cases.',
      classification: 'outlier',
      members: [
        {
          source_id: 's2',
          stance: 'supports',
          claim_text: 'Rare autoimmune events documented in 0.001% of recipients.',
          supporting_quote: 'Rare adverse events were recorded in a small cohort.',
          confidence: 'low',
        },
      ],
    },
  ],
  gaps: [
    {
      description: 'Long-term efficacy beyond 12 months',
      rationale: 'No source covered outcomes beyond one year post-vaccination.',
    },
  ],
  meta: {
    sources_ok: 2,
    sources_failed: 1,
    model_reason: 'claude-3-5-sonnet',
    model_extract: 'claude-3-haiku',
  },
}
