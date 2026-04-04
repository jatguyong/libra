import re
from pathlib import Path
from neo4j import GraphDatabase

filepath = Path(r'c:\Users\John Reniel\libra-1\neo4j_kbpedia\kbpedia_reference_concepts_linkage.n3')
print(f'Parsing {filepath}')

updates = []

with open(filepath, 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if 'owl:equivalentClass' in line and 'wikidata.org/entity/Q' in line:
            m = re.search(r'<http://www.wikidata.org/entity/(Q\d+)>\s+owl:equivalentClass\s+<http://kbpedia.org/kko/rc/([^>]+)>', line)
            if m:
                qid = m.group(1)
                rc = m.group(2)
                uri = 'http://kbpedia.org/kko/rc/' + rc
                updates.append({'uri': uri, 'qid': qid})

print(f'Found {len(updates)} QID mappings. Updating Neo4j...')

driver = GraphDatabase.driver('neo4j://127.0.0.1:7687', auth=('neo4j', 'graphrag'))
with driver.session(database='neo4j') as session:
    batch_size = 5000
    for i in range(0, len(updates), batch_size):
        batch = updates[i:i+batch_size]
        query = '''
        UNWIND $batch as row
        MATCH (n:KBPediaConcept {uri: row.uri})
        SET n.wikidata_qid = row.qid
        '''
        session.run(query, batch=batch)
        print(f'Updated batch {i//batch_size + 1}/{len(updates)//batch_size + 1}')

print('Done!')
