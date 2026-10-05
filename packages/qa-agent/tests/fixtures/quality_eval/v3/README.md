# Q02a development baseline v3

Explicit opt-in only; default remains v1. Prior v1/v2 are immutable and reject
new production source drift. Original queries, top-k, retrieval labels, scoring
definitions and six assessment controls are inherited without changes.

Nine separately labeled developer-authored fake-client multi-turn controls run
the actual ChatAgent. Their denominator is nine scenarios, not provider quality
or independent/human gold. Source freeze references an already-existing local
production commit. Runtime import-root guards remain enabled.

Only adjacent, one-use text-only hero attribute references are included. The
white-list parser accepts 他 or 该武将, optional 的, one of 初始/基础/满级/成长,
one of 武力/智力/统率/先攻, optional 是, 多少, and at most one ？/?/。.
Outer whitespace is stripped; internal spaces/additional clauses are outside it.

An eligible preceding seed is a full-match bare canonical name/unique alias,
or that name plus the same optional 的 / stage / attribute / optional 是 / 多少
suffix; both permit at most one terminal ？/?/。. Other single-turn questions
still answer normally but cannot establish this private referent binding.
Eligible hero records require hero domain, hero_profile kind and HeroStaticProfile
data together. Merely mentioning a name or carrying hero-shaped generic data is
not sufficient. The source freeze is explicitly rebound after local CR repair;
the original unpublished v3 source binding remains in Git history.
