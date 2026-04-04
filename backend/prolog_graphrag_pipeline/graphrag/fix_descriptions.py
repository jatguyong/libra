import re
from pathlib import Path
from neo4j import GraphDatabase

filepath = Path(r'c:\Users\John Reniel\libra-1\neo4j_kbpedia\kbpedia_reference_concepts_linkage.n3')
print(f'Parsing {filepath}')

updates = []
current_uri = None

with open(filepath, 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line.startswith(':'):
            match = re.search(r'^:([A-Za-z0-9_-]+)\s+a\s+owl:Class', line)
            if match:
                current_uri = "http://kbpedia.org/kko/rc/" + match.group(1)
            else:
                current_uri = None
        
        if current_uri and "skos:definition" in line:
            m = re.search(r'skos:definition\s+"(.*?)"@en', line)
            if m:
                new_def = m.group(1).replace('\\"', '"').replace("\\'", "'")
                updates.append({'uri': current_uri, 'definition': new_def})

print(f'Found {len(updates)} definitions. Updating Neo4j...')

driver = GraphDatabase.driver('neo4j://127.0.0.1:7687', auth=('neo4j', 'graphrag'))
with driver.session(database='neo4j') as session:
    batch_size = 5000
    for i in range(0, len(updates), batch_size):
        batch = updates[i:i+batch_size]
        query = '''
        UNWIND $batch as row
        MATCH (n:KBPediaConcept {uri: row.uri})
        SET n.definition = row.definition
        '''
        session.run(query, batch=batch)
        print(f'Updated batch {i//batch_size + 1}/{len(updates)//batch_size + 1}')

print('Done!')
