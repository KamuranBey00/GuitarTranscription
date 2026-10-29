import functools
import sys

import gtab.models.rhythm_net as R
import gtab.pipeline as P

P.separate_strings = functools.partial(R.separate_strings, move="weaker")
if sys.argv[1] == "score":
    import scripts.eval.eval_score as E
    E.main(None)
else:
    import scripts.eval.gv.clash_rhythm as C
    C.main(None)
