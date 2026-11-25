# CBT-1: Continuation Boundary Transfer

**Sharthok Rayan Pal · November 25, 2026 · Protocol 1.0.0**

Does a fixed prerequisite that suppresses answer text also suppress a structured function-call proposal? CBT-1 schedules 1,000 fresh Chat Completions requests to `gpt-5.2-2025-12-11`. For every paired comparison the messages and model settings are identical. One request exposes an inert function. The other omits tools. No proposed function is executed.

Read [PROTOCOL.md](PROTOCOL.md) for the intervention, exclusions, predictions, exact test, cost rules and stop rules. [schedule.tsv](schedule.tsv) freezes every slot. [requests/](requests/) contains all twelve exact HTTP request bodies. [predictions.json](predictions.json) fixes all thresholds before dispatch.

## Offline reproduction

Python 3.9 or later, standard library. The following commands make no API requests.

```sh
git clone --branch v1.0.0 https://github.com/theonlypal/cbt-1-preregistration.git
cd cbt-1-preregistration
python3 -B common.py check .
python3 -B verify_design.py
python3 -B -m unittest -v test_cbt
```

With a published results checkout at a sibling path:

```sh
python3 -B verify.py ../cbt-1-results/run
```

To regenerate the tables independently in a scratch copy, copy the evidence to a new directory, run `python3 -B analysis.py /path/to/copy`, then `python3 -B verify.py /path/to/copy`. Compare the files in `analysis/` with the originals. The verifier reads the saved raw bytes. Its observation decoder and statistical calculations are separate from the recorder and primary analysis.

## Frozen sources

- [Root Matrix protocol and original Unicode strings](https://github.com/theonlypal/root-matrix-cross-protocol-preregistration/blob/633898463c02b249698bc1bb08711e29ab1d99a5/study/strings.json)
- [Root Matrix paired results](https://github.com/theonlypal/root-matrix-cross-protocol-results/tree/8c7843438256d73b9ca694d05c8da29428590b7c)
- [RP-GATE-1 results](https://github.com/theonlypal/rp-gate-1-results/tree/e3cecfc4feb86e4bdf4235bb5380dadd73d5f934)
