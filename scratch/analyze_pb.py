import json

with open('data/cache/pre_breakout_result.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

results = d.get('results', [])
criteria_stats = {f'k{i}': {'pass': 0, 'fail': 0, 'title': ''} for i in range(1, 8)}

for r in results:
    cr = r.get('criteria', {})
    for k, v in cr.items():
        if k in criteria_stats:
            criteria_stats[k]['title'] = v.get('title', k)
            if v.get('pass'):
                criteria_stats[k]['pass'] += 1
            else:
                criteria_stats[k]['fail'] += 1

print(f"Total candidates analyzed: {len(results)}")
for k, s in sorted(criteria_stats.items()):
    pct = (s['pass'] / len(results)) * 100 if results else 0
    print(f"{k}: {s['title']:<38} | PASS: {s['pass']:>2} ({pct:>5.1f}%) | FAIL: {s['fail']:>2}")

# Let's inspect distribution of scores
scores = {}
for r in results:
    sc = r.get('total_score', 0)
    scores[sc] = scores.get(sc, 0) + 1
print("\nScore Distribution:")
for sc in sorted(scores.keys(), reverse=True):
    print(f"Score {sc}/7: {scores[sc]} stocks")

# Let's see what criteria fail most often for score 6
print("\nFailed criteria on Score 6/7:")
score_6_fails = {}
for r in results:
    if r.get('total_score') == 6:
        for k, v in r.get('criteria', {}).items():
            if not v.get('pass'):
                score_6_fails[k] = score_6_fails.get(k, 0) + 1
for k, count in sorted(score_6_fails.items()):
    print(f"{k} ({criteria_stats[k]['title']}): failed by {count} stocks")
