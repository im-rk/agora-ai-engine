"""
Adjudication Prompts: 5-Phase Hybrid-Weighted Evaluation Algorithm.

Phase 1: Neutral Theme Extraction - Extract macro-clashes
Phase 2: Weighted Clash Matrix - Build WCM with weights and deltas
Phase 3: Mathematical Breakdown - Calculate Net Logic Score
Phase 4: WUDC Pillar Analysis - Grade Matter, Manner, Method, Role
Phase 5: Structured Output - Generate JSON with CoT reasoning
"""


MACRO_CLASH_EXTRACTION_PROMPT = """You are an expert debate analyst evaluating a Parliamentary debate.

Your task: Extract the 3-5 core macro-themes (clashes) that defined this debate.

A macro-clash is a fundamental disagreement between teams (e.g., "Does the resolution expand power responsibly?")
NOT a specific argument, but the THEME that multiple arguments orbited around.

Debate transcript:
{transcript}

Output format (JSON only):
{{
    "clashes": [
        {{
            "id": 1,
            "theme": "The Economic Impact Clash",
            "description": "Did the resolution's policy improve or harm the economy?",
            "government_position": "Brief summary",
            "opposition_position": "Brief summary"
        }},
        ... (3-5 total)
    ]
}}

Rules:
1. Clashes must be THEMATIC, not specific arguments
2. Each clash must have clear positions from both teams
3. Order clashes by importance (most impactful first)
4. Output ONLY valid JSON. No explanations, no markdown."""


WEIGHTED_CLASH_MATRIX_PROMPT = """You are a debate mathematician calculating the Weighted Clash Matrix (WCM).

For each macro-clash identified in the debate, you will:
1. Assign a WEIGHT (1-5): How important is this clash to the debate outcome?
   - 1 = Peripheral issue, won or lost doesn't swing the debate
   - 5 = Central to the motion, whoever wins this wins the debate
   
2. Assign a DELTA (-2 to +2): Which team won this clash?
   - -2 = Opposition crushed Government
   - -1 = Opposition slightly won
   -  0 = Tie/Unclear
   - +1 = Government slightly won
   - +2 = Government crushed Opposition

Macro-clashes to evaluate:
{clashes}

Debate transcript:
{transcript}

Output format (JSON only):
{{
    "wcm_matrix": [
        {{
            "clash_id": 1,
            "clash_theme": "The Economic Impact Clash",
            "weight": 4,
            "weight_reasoning": "This is central to the resolution's core impact",
            "delta": 1,
            "delta_reasoning": "Government provided stronger economic evidence",
            "weighted_score": 4  // = weight * delta
        }},
        ... (one per clash)
    ],
    "net_logic_score": 5  // SUM of all weighted_scores
}}

Rules:
1. Weight must be 1-5 (integer)
2. Delta must be -2, -1, 0, +1, or +2 (integer)
3. weighted_score = weight * delta (calculated automatically)
4. Provide clear reasoning for each weight and delta
5. Output ONLY valid JSON. No explanations."""


WUDC_PILLAR_ANALYSIS_PROMPT = """You are a WUDC debate judge evaluating debate quality using the 4 pillars:

1. MATTER (Logic): Did they win the actual arguments? (Based on WCM math)
2. MANNER (Delivery): Was their delivery persuasive? Calm, authoritative, natural?
3. METHOD (Structure): Was their case organized? Did they extend/clash properly?
4. ROLE (Rules): Did each speaker fulfill their role? Stay on time? Follow debate convention?

Macro-clashes and WCM scores:
{wcm_matrix}

Net Logic Score: {net_logic_score}

Debate transcript:
{transcript}

Speaker breakdown (roles and number of turns):
{speaker_info}

Output format (JSON only):
{{
    "pillars": {{
        "matter": {{
            "definition": "Logic: Won the mathematical WCM",
            "government_score": 25,
            "opposition_score": 20,
            "reasoning": "Government won key clashes 4-3 on WCM"
        }},
        "manner": {{
            "definition": "Delivery: Persuasive and natural speaking",
            "government_score": 20,
            "opposition_score": 18,
            "reasoning": "Government speakers more authoritative, Opposition slightly defensive"
        }},
        "method": {{
            "definition": "Structure: Organized case with clear impacts",
            "government_score": 18,
            "opposition_score": 22,
            "reasoning": "Opposition had tighter case structure, Government more scattered"
        }},
        "role": {{
            "definition": "Role: Fulfilled speaker responsibilities",
            "government_score": 12,
            "opposition_score": 15,
            "reasoning": "Both followed convention, Opposition managed time better"
        }}
    }},
    "pillar_reasoning": "Although Government won the WCM (Matter), Opposition's superior Method and Role adherence made it competitive"
}}

Rules:
1. Matter score: Award points based on NET_LOGIC_SCORE (winning team gets 20-25, losing gets 10-20)
2. Manner, Method, Role: Each 0-25, independent of Matter
3. Totals: Government total = matter + manner + method + role (same for Opposition)
4. Each pillar score must explain the reasoning
5. Maximum per team: 100 points (25 per pillar)
6. Output ONLY valid JSON."""


SPEAKER_PERFORMANCE_PROMPT = """You are grading individual speakers on their specific performance.

Debate format: {format}
Speaker roles: {speaker_roles}

Macro-clashes: {clashes}
Pillar scores: {pillar_scores}

Debate transcript:
{transcript}

For EACH speaker, assign a score (0-100) based on:
- Argument quality (did they explain well?)
- Evidence usage (did they have facts?)
- Responsiveness (did they answer opponents?)
- Structure (was their speech organized?)
- Persona fit (did they stay in character?)

Output format (JSON only):
{{
    "speaker_scores": [
        {{
            "role": "Prime Minister",
            "side": "Government",
            "score": 78,
            "argument_quality": 8,
            "evidence_usage": 7,
            "responsiveness": 8,
            "structure": 8,
            "persona": 9,
            "feedback": "Strong opening, good evidence, but missed key Opposition point on impact"
        }}
    ]
}}

Rules:
1. Final score = (argument + evidence + responsiveness + structure + persona) * 2
2. Each component 0-10
3. Provide constructive, specific feedback
4. Output ONLY valid JSON."""


FINAL_ADJUDICATION_SUMMARY_PROMPT = """You are writing the final adjudication summary.

WCM Results: {wcm_summary}
Pillar Breakdown: {pillar_breakdown}
Speaker Scores: {speaker_scores}

Write a brief (150-200 word) adjudication statement explaining:
1. Which team won and why
2. The key decision points (top 2-3 clashes)
3. Any standout performances
4. One development each team should work on

This will be read by the user. Be fair, constructive, and clear.

Format:
{{
    "adjudication": "Detailed statement here...",
    "key_decision_1": "Theme and explanation",
    "key_decision_2": "Theme and explanation",
    "key_decision_3": "Theme and explanation"
}}

Rules:
1. Output ONLY valid JSON.
2. Do not include markdown code blocks like ```json.
3. Do not include any text or explanations outside the JSON object."""
