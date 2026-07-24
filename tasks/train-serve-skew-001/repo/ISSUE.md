# Online predictions depend on who else is in the request batch

Training uses `fit_standardizer` and saves its statistics, but `transform` ignores
those statistics and refits on the inference batch. The same observation can
therefore receive different features depending on neighboring requests.

Repair the module so that:

- `transform` uses only the supplied training statistics.
- Feature order follows the supplied `features` sequence.
- Population standard deviation is used; constant features receive scale `1.0`.
- Empty training data, duplicate feature names, and missing features fail clearly.
- Inputs and saved statistics are not mutated.
- No third-party dependencies are added.

