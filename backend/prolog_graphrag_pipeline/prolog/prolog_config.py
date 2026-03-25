# Global configuration toggle for dynamic Wikidata fetching

# Global configuration toggle for dynamic Wikidata fetching
ENABLE_WIKIDATA_FETCHING = True

GENERATOR_SYSTEM_PROMPT = r"""
### Role
You are an expert Prolog programmer specializing in Knowledge Representation for the s(CASP) solver.

### Input Structure
You will receive five distinct pieces of information to build your logic from:
1. **User Question**: The primary question to solve, which can be yes/no or explanatory question.
2. **Atomic Facts**: Unconditional, standalone truths extracted from the source material.
3. **Conditional Rules**: Causal relationships, laws, or theorems formatted as IF-THEN statements.
4. **Exceptions**: Boundary conditions, caveats, or limitations to the rules.
5. **Logical Gaps**: Missing premises or external requirements identified during extraction.

### Task
Translate the provided inputs into a formal Prolog database. Generate rules (Head :- Body.) rather than just facts.

**CRITICAL FALLBACK INSTRUCTION**: If the four context fields (Facts, Rules, Exceptions, Gaps) are empty, return "None", or lack sufficient information to prove the query, you MUST rely entirely on your own internal expert knowledge to generate the correct clauses, rules, and query. Do not overthink or fail if the explicit context is missing; simply formulate the standard domain logic and commonsense rules required to definitively answer the User Question.

### Execution Flow
1. Start with a <planning> block. Explicitly map out the logical architecture: identify the target query, the grounded facts you have (or need to supply from internal knowledge), and the specific IF-THEN rules required to connect those facts to the query. 
2. Use a SEPARATE <reasoning_step> tag for each logical leap. Explain in English, then provide Prolog code snippets.
3. Formulate implicit domain rules if necessary.
4. Output the full <database>.
5. Output the <query>.

### Syntactic Requirements (s(CASP) Specific)
- Disjunction: NEVER use `;`. Use multiple separate rules with the same head instead.
- Arithmetic & Evaluation: s(CASP) does NOT support standard Prolog arithmetic evaluation.
   - NEVER use `is`, `=`, `>=`, `=:=`, `=\=`, `<`, `>`, `<=`.
   - USE CLP(Q) constraints instead: `#=`, `#<>`, `#<`, `#>`, `#=<`, `#>=`. Example: `X #= Y + 1`.
- Negation: Use `not`. NEVER use `\+`.
- Classical Negation: Use `-` prefix (e.g., `-mortal(X).`).
- Banned Predicates: NEVER use `option`. It conflicts with the SWI-Prolog standard library. If writing an MCQ, use `choice` instead.
- Atoms: MUST be lowercase snake_case with underscores replacing spaces (e.g., `cell_wall`, `cell_membrane`). NEVER use spaces inside atoms — `choice(a, cell membrane)` is a SYNTAX ERROR. Write `has_part(cell, cell_membrane)` instead.
- Grounding: EVERY fact argument must be a lowercase atom. NEVER start a fact argument with an Uppercase letter unless you explicitly intend it to be a variable. CamelCase names (e.g., `PlantCell`) are treated as Variables and will break the logic.
- Variables: MUST start with an Uppercase letter (e.g., `X`, `Animal`). 
- Meaningful Atoms: Use snake_case atoms that accurately reflect the phrasing in the text. Condense long phrases into 3-5 critical words (e.g., `eliminating_a_source_from_consideration` -> `eliminate_source`). The meaning must remain clear.
- Closed-World: EVERY predicate in a body MUST be defined as a fact or rule head somewhere in the database.
- Contiguous: Group ALL clauses for the same predicate together. Do NOT alternate between predicates (e.g., `p(a). q(b). p(c).` is forbidden; write `p(a). p(c). q(b).` instead).
- Predicate Naming: ALWAYS invent meaningful predicate names that accurately describe the relationships in the specific question. NEVER blindly copy predicate names (like `forms_from`) or structures from the few-shot examples unless they are directly relevant.

### Query Formatting by Question Type
1. **Multiple-Choice Questions (MCQ):**
   - A question is only multiple-choice if it has a number of lettered options (e.g. "A. gravity B. weak nuclear force C. strong nuclear force D. electromagnetism").
   - Encode EXACTLY FOUR choices as facts. The description MUST be a grounded lowercase snake_case atom derived from the ACTUAL option text, NEVER an uppercase variable!
   - Example CORRECT: `choice(a, eliminating_a_source).`
   - Example WRONG: `choice(a, A).` (This will trivially unify with anything and fail the proof!)
   - Encode retrieved domain knowledge as facts and rules.
   - You MUST define an `answer/1` rule that unifies with the correct option letter.
   - **CRITICAL:** Your logic MUST uniquely identify EXACTLY ONE correct choice. Do not write generic rules that might accidentally evaluate to true for multiple incorrect options. You must explicitly differentiate the correct target from the distractors based on the domain rules.
   - Example DB Rule: `answer(OptionLetter) :- choice(OptionLetter, Target), matches_criteria(Target).`
   - IF the question is an MCQ, the <query> MUST strictly be: answer(OptionLetter). Do NOT use this format for Binary or Freeform questions.
2. **Binary (True/False) Questions:**
   - A question is only binary if it asks whether a certain condition holds or not -- where you can only answer "yes" or "no".
   - Define specific instances from the question (e.g., `rock_one`, `rock_two`).
   - Write rules defining the condition context (e.g., `pulled_together(A, B) :- ...`).
   - The <query> MUST test the fully grounded relationship directly (e.g., `pulled_together(rock_one, rock_two).`).
3. **Freeform / Explanatory:**
   - A question is free-form only if either it doesn't have explicit multiple choices or if it specifically asks you the "why" behind a certain phenomenon or concept.
   - Define facts, relationships and rules using the atomic facts, conditional rules, and exceptions. If there are any logical gaps, rely on your knowledge to generate more facts or rules necessary to answer the question.
   - The <query> queries the primary target entity state.

### Warning Avoidance (CRITICAL)
- **AVOID SINGLETON VARIABLES WARNINGS**: In Prolog, a singleton variables warning triggers when a variable appears exactly once in a clause. This usually indicates a logical error. To prevent this:
  1. **Never capitalize atoms:** `can_be_controlled(RecordingObservations).` treats `RecordingObservations` as a variable. If it's only used once, it triggers a singleton warning. Always use lowercase `recording_observations`.
  2. **Prefix unused variables with an underscore:** If a rule requires a variable that is only used once in that specific clause, you MUST prefix it with an underscore (e.g., `_Target`) or use the anonymous variable `_`. Example CORRECT: `is_colored(Item) :- has_property(Item, _Color).` Example WRONG: `is_colored(Item) :- has_property(Item, Color).`
- **STRICT CONTIGUITY (Prolog Linter)**: You MUST group all clauses of the same predicate together sequentially. Do NOT alternate between different predicates. 
  - WRONG: `p(a). q(b). p(c).`
  - CORRECT: `p(a). p(c). q(b).`
- **SORTING**: In your `<database>` block, it is recommended to sort your predicates alphabetically or by logical group to ensure all clauses for the same predicate are together. This prevents "Discontiguous" warnings which can cause SWI-Prolog to ignore parts of the database.

### Output Format (Strict)
<planning>
[1. Question Type: Explicitly state if the User Question is MCQ, Binary, or Freeform based on the rules above.]
[2. Architecture: Map out the target query format specific to that question type.]
[3. Logic: State the grounded facts you have and the rules needed to bridge them.]
</planning>

<reasoning_step>
[Reasoning in English]
[Prolog code snippets]
</reasoning_step>

<database>
[All facts and rules combined]
</database>

<query>
[The query only]
</query>

### CRITICAL FINAL REMINDERS (DO NOT IGNORE):
1. NO STANDARD ARITHMETIC ALLOWED: You MUST use CLP(FD) operators `#> `, `#>= `, `#< `, `#=< `, `#= ` for ALL math. `>` and `<` will instantly crash the parser!
2. CONTIGUOUS CLAUSES: Group ALL rules and facts that share the same predicate name together in the `<database>`. Do NOT scatter them.
---

### FINAL VALIDATION CHECKLIST (RUN BEFORE OUTPUT)

Verify the following:

✓ <planning> block is included and logically sound
✓ Your database and query are appropriate for the question type
✓ No `;`
✓ No `is`, `<`, `>`, `>=`, `=<`
✓ Only CLP operators (`#=`, `#>`, etc.)
✓ No `\+`
✓ No `option`
✓ All atoms are lowercase snake_case
✓ Singletons (variables appearing only once) are prefixed with `_`
✓ No undefined predicates
✓ Clauses are contiguous
✓ Exactly four `choice/2` facts for MCQ
✓ Query matches the required format

If any rule fails, correct the program before producing the final output.
"""

# ─────────────────────────────────────────────────────────────────
#  Typed few-shot example banks  (keyed by question_type)
# ─────────────────────────────────────────────────────────────────

BINARY_FEW_SHOT_EXAMPLES = [
    # Example B-1: Binary — Food web contamination
    {"role": "user", "content": """
Now, process the following:

User Question: If the grass is contaminated, are the snakes affected?

Context:
**ATOMIC FACTS**:
    - In a food web, grass is a producer.
    - Grasshoppers eat grass.
    - Frogs eat grasshoppers.
    - Snakes eat frogs.

**CONDITIONAL RULES**:
    - None

**EXCEPTIONS**:
    - None

**LOGICAL GAPS**:
    - None
"""},
    {"role": "assistant", "content": r"""
<planning>
1. Question Type: Binary — the user asks whether a condition (snakes being affected) holds. Query: `affected(snake).`
2. Architecture: Test the fully grounded entity state.
3. Grounded Facts: food chain eats/2 relationships + is_contaminated(grass).
</planning>

<reasoning_step>
Encode relationships and premise.
eats(grasshopper, grass).
eats(frog, grasshopper).
eats(snake, frog).
is_contaminated(grass).
</reasoning_step>

<reasoning_step>
Contamination logic — recursive propagation.
affected(Species) :- is_contaminated(Species).
affected(Predator) :- eats(Predator, Prey), affected(Prey).
</reasoning_step>

<database>
eats(grasshopper, grass).
eats(frog, grasshopper).
eats(snake, frog).
is_contaminated(grass).

affected(Species) :- is_contaminated(Species).
affected(Predator) :- eats(Predator, Prey), affected(Prey).
</database>

<query>
affected(snake).
</query>
---
"""},

    # Example B-2: Binary — Magnetic force
    {
        "role": "user",
        "content": """
Now, process the following:
User Question:
If two rocks are lacking magnetic properties and far apart, can a magnetic effect pull them together?

Context:
**ATOMIC FACTS**:
    - A magnetic effect can pull two objects together.

**CONDITIONAL RULES**:
    - Magnetic properties are necessary for a magnetic force to act between two rocks.
    - Rocks that lack magnetic properties will not be pulled towards each other by magnetism.
    - If an object has magnetic properties, it may exert a magnetic force on another object with similar properties.

**EXCEPTIONS**:
    - None

**LOGICAL GAPS**:
    - None
        """
    },
    {
        "role": "assistant",
        "content": r"""
<planning>
1. Question Type: Binary — tests whether the grounded relationship pulled_together(rock_one, rock_two) holds.
2. Architecture: Query the fully grounded relationship directly.
3. Logic: Both rocks lack magnetic properties, so the classical negation rule fires; the positive rule cannot fire.
</planning>

<reasoning_step>
Encode specific instances.
lacks_magnetic_properties(rock_one).
lacks_magnetic_properties(rock_two).
far_apart(rock_one, rock_two).
</reasoning_step>

<reasoning_step>
Explicit falsehood limits.
-pulled_by_magnetism(RockA, _) :- lacks_magnetic_properties(RockA).
-pulled_by_magnetism(_, RockB) :- lacks_magnetic_properties(RockB).
</reasoning_step>

<reasoning_step>
Positive conditions.
pulled_together(ObjectA, ObjectB) :-
has_magnetic_properties(ObjectA),
has_magnetic_properties(ObjectB).
</reasoning_step>

<database>
lacks_magnetic_properties(rock_one).
lacks_magnetic_properties(rock_two).
far_apart(rock_one, rock_two).

-pulled_by_magnetism(RockA, _) :- lacks_magnetic_properties(RockA).
-pulled_by_magnetism(_, RockB) :- lacks_magnetic_properties(RockB).

pulled_together(ObjectA, ObjectB) :-
has_magnetic_properties(ObjectA),
has_magnetic_properties(ObjectB).
</database>

<query>
pulled_together(rock_one, rock_two).
</query>
---
"""
    },

    # Example B-3: Binary — Proton magnetic force direction
    {
        "role": "user",
        "content": """
Now, process the following:

Question: A proton is moving horizontally to the right through a uniform magnetic field that is directed perpendicular to the proton's velocity and straight into the page. Does the proton experience an upward magnetic force?

Context:
**ATOMIC FACTS**:
   - The particle in motion is a proton.
   - A proton is a positively charged particle.
   - The velocity vector of the particle is directed to the right.
   - The magnetic field vector is directed into the page.

**CONDITIONAL RULES**:
   - None

**EXCEPTIONS**:
   - None

**LOGICAL GAPS**:
   - The context does not provide the Right-Hand Rule (Lorentz force vector cross product) required to determine the spatial direction of the magnetic force exerted on a moving charge.
        """
    },
    {
        "role": "assistant",
        "content": r"""
<planning>
1. Question Type: Binary — tests a specific spatial relationship. Query: `experiences_force_direction(proton, up).`
2. Architecture: Grounded test of whether the force direction holds.
3. Logic: Use internal knowledge of the Right-Hand Rule to supply the missing conditional.
</planning>

<reasoning_step>
Encode atomic facts.
charge(proton, positive).
magnetic_field_direction(into_page).
velocity_direction(proton, right).
</reasoning_step>

<reasoning_step>
Bridge logical gap with Right-Hand Rule.
experiences_force_direction(Particle, up) :-
    charge(Particle, positive),
    velocity_direction(Particle, right),
    magnetic_field_direction(into_page).
</reasoning_step>

<database>
charge(proton, positive).
magnetic_field_direction(into_page).
velocity_direction(proton, right).

experiences_force_direction(Particle, up) :-
    charge(Particle, positive),
    velocity_direction(Particle, right),
    magnetic_field_direction(into_page).
</database>

<query>
experiences_force_direction(proton, up).
</query>
---
"""
    },
]


MCQ_FEW_SHOT_EXAMPLES = [
    # Example M-1: MCQ — Pot handle material
    {
        "role": "user",
        "content": """
Now, process the following:

User Question: A chef needs to pick a material for a pot handle that stays cool while cooking. Which material would be the best choice?
A. copper
B. aluminum
C. wood
D. steel

Context:
**ATOMIC FACTS**:
    - Metals are good conductors of heat.
    - Metals contain free-moving electrons.
    - Wood is a poor conductor of heat.
    - Wood's molecules are tightly bound.
    - Rubber is an insulator.
    - Glass conducts heat poorly.

**CONDITIONAL RULES**:
    - Free-moving electrons transfer kinetic energy quickly.
    - Molecules that are tightly bound do not transfer energy efficiently.

**EXCEPTIONS**:
    - None

**LOGICAL GAPS**:
    - None
"""},
    {
        "role": "assistant",
        "content": r"""
<planning>
1. Question Type: MCQ — the question lists exactly four lettered options. Query MUST be `answer(OptionLetter).`
2. Architecture: Encode choice/2 facts + domain rules; define answer/1 rule.
3. Logic: wood is the only insulator among the options, so it stays cool.
</planning>

<reasoning_step>
Encode the four choices.
choice(a, copper).
choice(b, aluminum).
choice(c, wood).
choice(d, steel).
</reasoning_step>

<reasoning_step>
Encode conductivity from context and internal knowledge.
is_conductor(copper).
is_conductor(aluminum).
is_conductor(steel).
is_insulator(wood).
</reasoning_step>

<reasoning_step>
Bridging rule: insulator stays cool.
stays_cool(Material) :- is_insulator(Material).
answer(OptionLetter) :- choice(OptionLetter, Material), stays_cool(Material).
</reasoning_step>

<database>
choice(a, copper).
choice(b, aluminum).
choice(c, wood).
choice(d, steel).

is_conductor(copper).
is_conductor(aluminum).
is_conductor(steel).
is_insulator(wood).

stays_cool(Material) :- is_insulator(Material).

answer(OptionLetter) :- choice(OptionLetter, Material), stays_cool(Material).
</database>

<query>
answer(OptionLetter).
</query>
---
"""
    },

    # Example M-2: MCQ — Intermolecular forces
    {
        "role": "user",
        "content": """
Now, process the following:

User Question: Based on the dominant intermolecular forces present, which of the following substances will require the greatest amount of thermal energy to undergo a phase transition from liquid to gas at standard pressure?
A. methane
B. hydrogen sulfide
C. water
D. neon

Context:
**ATOMIC FACTS**:
   - Water molecules exhibit hydrogen bonding.
   - Methane molecules exhibit only London dispersion forces.
   - Hydrogen sulfide molecules exhibit dipole-dipole interactions.
   - Neon atoms exhibit only London dispersion forces.
   - Hydrogen bonding is a stronger intermolecular force than both dipole-dipole interactions and London dispersion forces.
   - A stronger intermolecular force requires a greater amount of thermal energy to overcome.

**CONDITIONAL RULES**:
   - None

**EXCEPTIONS**:
   - None

**LOGICAL GAPS**:
   - None
        """
    },
    {
        "role": "assistant",
        "content": r"""
<planning>
1. Question Type: MCQ — four lettered options present. Query: `answer(OptionLetter).`
2. Architecture: choice/2 facts + IMF strength facts + bridging rule.
3. Logic: hydrogen bonding > dipole-dipole > LDF; water has hydrogen bonding → requires greatest energy.
</planning>

<reasoning_step>
Encode the four choices.
choice(a, methane).
choice(b, hydrogen_sulfide).
choice(c, water).
choice(d, neon).
</reasoning_step>

<reasoning_step>
Encode IMF facts.
has_imf(hydrogen_sulfide, dipole_dipole).
has_imf(methane, london_dispersion).
has_imf(neon, london_dispersion).
has_imf(water, hydrogen_bond).

stronger_than(hydrogen_bond, dipole_dipole).
stronger_than(hydrogen_bond, london_dispersion).
</reasoning_step>

<reasoning_step>
Bridging rule.
requires_greatest_energy(Substance) :- has_imf(Substance, hydrogen_bond).
answer(OptionLetter) :- choice(OptionLetter, Substance), requires_greatest_energy(Substance).
</reasoning_step>

<database>
choice(a, methane).
choice(b, hydrogen_sulfide).
choice(c, water).
choice(d, neon).

has_imf(hydrogen_sulfide, dipole_dipole).
has_imf(methane, london_dispersion).
has_imf(neon, london_dispersion).
has_imf(water, hydrogen_bond).

stronger_than(hydrogen_bond, dipole_dipole).
stronger_than(hydrogen_bond, london_dispersion).

requires_greatest_energy(Substance) :- has_imf(Substance, hydrogen_bond).

answer(OptionLetter) :- choice(OptionLetter, Substance), requires_greatest_energy(Substance).
</database>

<query>
answer(OptionLetter).
</query>
---
"""
    },

    # Example M-3: MCQ — Zero context fallback (Cellular respiration)
    {
        "role": "user",
        "content": """
Now, process the following:

User Question:
During aerobic cellular respiration, which of the following pathways directly acts as the final electron acceptor and consumes oxygen?
A. glycolysis
B. krebs cycle
C. electron transport chain
D. lactic acid fermentation

Context:
**ATOMIC FACTS**:
   - None

**CONDITIONAL RULES**:
   - None

**EXCEPTIONS**:
   - None

**LOGICAL GAPS**:
   - None
        """
    },
    {
        "role": "assistant",
        "content": r"""
<planning>
1. Question Type: MCQ — four lettered options. Query: `answer(OptionLetter).`
2. Architecture: choice/2 facts + internal knowledge fact + bridging rule.
3. Logic: All context is None; use internal knowledge. The electron transport chain directly consumes oxygen as final electron acceptor.
</planning>

<reasoning_step>
Encode the four choices as lowercase snake_case atoms.
choice(a, glycolysis).
choice(b, krebs_cycle).
choice(c, electron_transport_chain).
choice(d, lactic_acid_fermentation).
</reasoning_step>

<reasoning_step>
Internal knowledge fact.
consumes_oxygen_directly(electron_transport_chain).
</reasoning_step>

<reasoning_step>
Bridging rule.
answer(OptionLetter) :- choice(OptionLetter, Process), consumes_oxygen_directly(Process).
</reasoning_step>

<database>
choice(a, glycolysis).
choice(b, krebs_cycle).
choice(c, electron_transport_chain).
choice(d, lactic_acid_fermentation).

consumes_oxygen_directly(electron_transport_chain).

answer(OptionLetter) :- choice(OptionLetter, Process), consumes_oxygen_directly(Process).
</database>

<query>
answer(OptionLetter).
</query>
---
"""
    },
]


FREEFORM_FEW_SHOT_EXAMPLES = [
    # Example F-1: Freeform — Period T absolute value?
    {
        "role": "user",
        "content": """
Now, process the following:

User Question:
According to the provided texts, is the measured duration of an object's 'period' ($T$) considered to be an absolute value based on a fixed universal standard?

Context:
**ATOMIC FACTS**:
   * There are no true physical absolute measures.
   * No fixed frame of reference has been found.
   * The period of an object is measured in seconds and denoted by $T$.
   * The period $T$ is the time it takes for an object to complete a cycle.
**CONDITIONAL RULES**:
   * IF a force is applied to an object over a period of time, THEN the impulse is equal to the change in momentum.
   * IF an object moves around a full circle, THEN it completes a cycle and the time taken is called the period $T$.
**EXCEPTIONS**:
   * None
**LOGICAL GAPS**:
   * The definition of an absolute value in the context of the measured duration of an object's period $T$.
   * The relationship between the measured duration of an object's period $T$ and a fixed universal standard.
        """
    },
    {
        "role": "assistant",
        "content": r"""
<planning>
1. Question Type: Freeform/Explanatory — asks about the nature of a concept (absolute value). Query: `is_absolute_value(period_t).`
2. Architecture: Grounded entity state query — the query resolves because the conditions for absolute value are not met.
3. Logic: absolute measures and fixed frames don't exist → the bridging rule for is_absolute_value fires only when they do → result is false.
</planning>

<reasoning_step>
Encode the facts from the context.
measure(period_t).
absolute_measures_exist(false).
fixed_frame_of_reference_exists(false).
</reasoning_step>

<reasoning_step>
Bridging rule — absolute value requires both conditions to be true.
is_absolute_value(M) :-
measure(M),
absolute_measures_exist(true),
fixed_frame_of_reference_exists(true).
</reasoning_step>

<database>
measure(period_t).
absolute_measures_exist(false).
fixed_frame_of_reference_exists(false).

is_absolute_value(M) :-
measure(M),
absolute_measures_exist(true),
fixed_frame_of_reference_exists(true).
</database>

<query>
is_absolute_value(period_t).
</query>
"""
    },

    # Example F-2: Freeform — Keratin chemical mechanism
    {
        "role": "user",
        "content": """
Now, process the following:

What specific chemical mechanism is used to link the foundational units of the material that reinforces skin cells and provides their toughness?

Context:
**ATOMIC FACTS**:
   * Skin cells need lots of the protein keratin.
   * Keratin is a protein that provides toughness to skin cells.
   * The matrix of bone cells consists of collagen hardened by calcium and phosphate crystals.
**CONDITIONAL RULES**:
   * IF a cell needs to perform a specific job, THEN it requires a specific protein.
   * IF a cell is a skin cell, THEN it needs lots of the protein keratin.
**EXCEPTIONS**:
   * None
**LOGICAL GAPS**:
   * The specific chemical mechanism used to link the foundational units of the material that reinforces skin cells is not mentioned in the provided context.
        """
    },
    {
        "role": "assistant",
        "content": r"""
<planning>
1. Question Type: Freeform/Explanatory — asks for a specific mechanism. Query: `chemical_mechanism(keratin, Mechanism).`
2. Architecture: Query unifies the variable Mechanism to capture the answer.
3. Logic: Rely on internal knowledge — keratin is a protein; proteins are built from amino acids linked by peptide bonds.
</planning>

<reasoning_step>
Encode extracted facts.
reinforces(keratin, skin_cells).
is_type(keratin, protein).
</reasoning_step>

<reasoning_step>
Internal knowledge fills the logical gap.
links_foundational_units(protein, peptide_bond).
</reasoning_step>

<reasoning_step>
Bridging rule.
chemical_mechanism(Material, Mechanism) :-
is_type(Material, Category),
links_foundational_units(Category, Mechanism).
</reasoning_step>

<database>
reinforces(keratin, skin_cells).
is_type(keratin, protein).

links_foundational_units(protein, peptide_bond).

chemical_mechanism(Material, Mechanism) :-
is_type(Material, Category),
links_foundational_units(Category, Mechanism).
</database>

<query>
chemical_mechanism(keratin, Mechanism).
</query>
"""
    },

    # Example F-3: Freeform — Avogadro's Law (gas particle comparison)
    {
        "role": "user",
        "content": """
Now, process the following:

User Question: What is true about the quantity of particles in a sample of carbon dioxide gas compared to a sample of ammonia gas if both samples occupy the same volume at identical temperature and pressure conditions?

Context:
**ATOMIC FACTS**:
   - Equal volumes of gases at the same temperature and pressure contain the same number of particles.

**CONDITIONAL RULES**:
   - IF two gas samples have the same volume, temperature, and pressure, THEN they contain the same number of particles (Avogadro's Law).

**EXCEPTIONS**:
   - None

**LOGICAL GAPS**:
   - None
        """
    },
    {
        "role": "assistant",
        "content": r"""
<planning>
1. Question Type: Freeform/Explanatory — asks what is true about a quantity comparison. This is NOT an MCQ; there are no lettered choices. Query: `particle_quantity_comparison(carbon_dioxide, ammonia, Relationship).`
2. Architecture: Query uses a variable to capture the relationship (same_number).
3. Logic: Avogadro's Law directly states that equal V, T, P → equal particle count.
</planning>

<reasoning_step>
Encode the gas samples and their conditions.
gas_sample(carbon_dioxide).
gas_sample(ammonia).
same_volume(carbon_dioxide, ammonia).
same_temperature(carbon_dioxide, ammonia).
same_pressure(carbon_dioxide, ammonia).
</reasoning_step>

<reasoning_step>
Encode Avogadro's Law as a conditional rule.
same_particle_count(GasA, GasB) :-
    gas_sample(GasA),
    gas_sample(GasB),
    same_volume(GasA, GasB),
    same_temperature(GasA, GasB),
    same_pressure(GasA, GasB).
</reasoning_step>

<reasoning_step>
Bridging rule to capture the relationship as a named atom.
particle_quantity_comparison(GasA, GasB, same_number) :-
    same_particle_count(GasA, GasB).
</reasoning_step>

<database>
gas_sample(ammonia).
gas_sample(carbon_dioxide).

same_pressure(carbon_dioxide, ammonia).
same_temperature(carbon_dioxide, ammonia).
same_volume(carbon_dioxide, ammonia).

same_particle_count(GasA, GasB) :-
    gas_sample(GasA),
    gas_sample(GasB),
    same_volume(GasA, GasB),
    same_temperature(GasA, GasB),
    same_pressure(GasA, GasB).

particle_quantity_comparison(GasA, GasB, same_number) :-
    same_particle_count(GasA, GasB).
</database>

<query>
particle_quantity_comparison(carbon_dioxide, ammonia, Relationship).
</query>
---
"""
    },
]


# ─────────────────────────────────────────────────────────────────
#  Dynamic message builder — called at generation time
# ─────────────────────────────────────────────────────────────────

def build_generator_messages(question_type: str) -> list:
    """
    Assemble the LLM message list for the Prolog generator, using ONLY
    the few-shot examples that match the detected question type AND
    a system prompt with irrelevant question-type sections removed.

    question_type: "mcq" | "binary" | "freeform"
    """
    if question_type == "mcq":
        few_shots = MCQ_FEW_SHOT_EXAMPLES
    elif question_type == "binary":
        few_shots = BINARY_FEW_SHOT_EXAMPLES
    else:
        few_shots = FREEFORM_FEW_SHOT_EXAMPLES

    # ── Build a type-specific system prompt ──────────────────────────
    system_prompt = GENERATOR_SYSTEM_PROMPT

    if question_type != "mcq":
        # Strip the entire MCQ section from "### Query Formatting by Question Type"
        import re as _re
        # Remove the MCQ block (section 1) — from "1. **Multiple-Choice" to just before "2. **Binary"
        system_prompt = _re.sub(
            r'1\.\s*\*\*Multiple-Choice Questions \(MCQ\)\:\*\*.*?(?=2\.\s*\*\*Binary)',
            '',
            system_prompt,
            flags=_re.DOTALL
        )
        # Remove the MCQ mention in Banned Predicates line
        system_prompt = system_prompt.replace(
            "- Banned Predicates: NEVER use `option`. It conflicts with the SWI-Prolog standard library. If writing an MCQ, use `choice` instead.",
            "- Banned Predicates: NEVER use `option`. It conflicts with the SWI-Prolog standard library."
        )
        # Remove the MCQ checklist item
        system_prompt = system_prompt.replace(
            "✓ Exactly four `choice/2` facts for MCQ\n",
            ""
        )
        # Add explicit anti-MCQ instruction at the end
        system_prompt += """
### QUESTION TYPE OVERRIDE
The current question is NOT a multiple-choice question. DO NOT generate `choice/2` facts or `answer(OptionLetter)` queries under any circumstances.
"""

    return (
        [{"role": "user", "content": system_prompt}]
        + few_shots
        + [
            {
                "role": "user",
                "content": (
                    "Acknowledge these strict Prolog generation instructions. "
                    "You must extract a formal Prolog <database> and <query> strictly "
                    "adhering to the s(CASP) syntactical constraints, with no standard "
                    "arithmetic, no singletons, and contiguous clauses."
                ),
            },
            {
                "role": "assistant",
                "content": (
                    "I understand and will follow all instructions strictly. I will generate "
                    "a syntactically valid s(CASP) Prolog program with a <reasoning_step>, "
                    "<database>, and <query>. I will strictly avoid forbidden operators like "
                    "`is`, `=\\=`, or `;`, and I will never use uppercase names for facts."
                ),
            },
        ]
    )


EXPLAINER_SYSTEM_PROMPT = rf"""
### Role
You are a Logical Translator. Take the formal output of a Prolog s(CASP) solver and transform it into a clear, step-by-step natural language explanation in relation to the query and to arrive at an answer.

### Core Objectives
Narrate the Proof: Walk through the s(CASP) justification tree. Explain exactly why the conclusion was reached using the retrieved facts. If s(CASP) returns False or uses `not`, explain it as an "absence of evidence."
Keep your explanations dense and easy to synthesize and understand.

### Syntactic Rules
- No Prolog Syntax: Use natural language only.
- Translate Predicates: You MUST silently translate all snake_case Prolog predicates and variables into normal English words. For example, change "has_complete_name" to "has complete name", and "historical_figure" to "historical figure".
- NO UNDERSCORES OR QUOTATIONS: Never output words with underscores or wrap rule names in quotation marks.
- Traceability: Keep the sequential logic. Do not jump straight to the conclusion.
"""

EXPLAINER_FEW_SHOT_EXAMPLES = [
    # Example 1
    {"role": "user", "content": rf"""
### DECODER TASK: ELUCIDATE LOGICAL PROOF
**USER QUESTION:**
If the grass is contaminated, are the snakes affected?

**RETRIEVED CONTEXT:**
In a food web, grass is a producer. Grasshoppers eat grass. Frogs eat grasshoppers. Snakes eat frogs.

**DATABASE:**

eats(grasshopper, grass). 
eats(frog, grasshopper). 
eats(snake, frog). 
is_producer(grass). 
is_contaminated(grass). 
affected(Species) :- is_contaminated(Species). 
affected(Predator) :- eats(Predator, Prey), affected(Prey). 
        

**QUERY**:
affected(snake).

**RETRIEVED VALUES**:
truth: True 

**s(CASP) HUMAN-READABLE EXPLANATION:**
   affected holds for snake, because
      eats holds for snake, and frog, and
      affected holds for frog, because
         eats holds for frog, and grasshopper, and
         affected holds for grasshopper, because
            eats holds for grasshopper, and grass, and
            affected holds for grass, because
               is_contaminated holds for grass

---
### INSTRUCTION:
Generate a coherent narrative of the proof above. Start with the conclusion, then detail the step-by-step logical path taken by the solver.
     """
     },
    {"role": "assistant", "content": """
**Conclusion:** Yes, the snakes are affected if the grass is contaminated.

**Logical Path:** The solver reached this conclusion by tracing the "flow" of contamination through the food web using a recursive logical chain:

1. **Source of Contamination:** The system first identifies that the grass (the producer) is explicitly contaminated. According to the primary rule, any species that is contaminated is considered "affected."

2. **The Consumption Chain:** The logic then uses a recursive rule: a predator is "affected" if it eats a prey that is already "affected." The solver traverses the food web step-by-step:

    - **Level 1:** The grasshopper eats the grass. Since the grass is affected, the grasshopper becomes affected.

    - **Level 2:** The frog eats the grasshopper. Since the grasshopper is now affected, the frog becomes affected.

    - **Level 3:** The snake eats the frog. Since the frog is affected, the snake finally becomes affected.

3. **Recursive Verification:** The s(CASP) solver linked the snake to the grass by verifying each "eats" relationship and carrying the "affected" status up through every level of the ecosystem.
     """
     },

     # Example 2
    {"role": "user", "content": rf"""
### DECODER TASK: ELUCIDATE LOGICAL PROOF
**USER QUESTION:**
Is Maria the grandmother of Dan?

**RETRIEVED CONTEXT:**
Maria is the mother of Chloe. Chloe is the mother of Dan.

**DATABASE:**

parent(maria, chloe). 
parent(chloe, dan). 
grandmother(Grandmother, Grandchild) :- parent(Grandmother, IntermediateParent), parent(IntermediateParent, Grandchild). 
        

**QUERY**:
grandmother(maria, dan). 

**RETRIEVED VALUES**:
truth: True 

**s(CASP) HUMAN-READABLE EXPLANATION:**
   grandmother holds for maria, and dan, because
      parent holds for maria, and chloe, and
      parent holds for chloe, and dan

---
### INSTRUCTION:
Generate a coherent narrative of the proof above. Start with the conclusion, then detail the step-by-step logical path taken by the solver.
     """
     },
    {"role": "assistant", "content": """
**Conclusion:** Yes, the logic confirms that Maria is the grandmother of Dan.

**Logical Path:** The solver reached this conclusion by identifying a direct connection between the individuals involved:

1. **Primary Rule:** The system defines a "grandmother" as someone who is the parent of a parent—an individual who is, in turn, the parent of the grandchild. This creates a logical chain requiring an "intermediate parent."
2. **The First Link (Generation 1):** The solver verifies the initial relationship that Maria is the parent of Chloe.
3. **The Second Link (Generation 2):** The solver then verifies the connecting relationship: Chloe is the parent of Dan.
4. **Verification of the Chain:** By identifying Chloe as the necessary intermediate link (the parent of Dan who connects Maria to Dan), the solver satisfies the requirement for the grandmother relationship.
     """
     },
]

EXPLAINER_LLM_MESSAGES = [
    {"role": "system", "content": EXPLAINER_SYSTEM_PROMPT}
] + EXPLAINER_FEW_SHOT_EXAMPLES

