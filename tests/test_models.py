""" UnitTest """
import unittest
import logging

import tweetnlp

logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s', level=logging.DEBUG, datefmt='%Y-%m-%d %H:%M:%S')

SAMPLE_NER = {'ner': ['Jacob Collier is a Grammy-awarded English artist from London.'] * 3}
SAMPLE_MLM = [
    "So glad I'm <mask> vaccinated.",
    "I keep forgetting to bring a <mask>.",
    "Looking forward to watching <mask> Game tonight!"
]
SAMPLE_CLASSIFICATION = {
    'sentiment': ["How many more days until opening day? 😩"] * 3,
    'offensive': ["All two of them taste like ass."] * 3,
    'irony': ["If you wanna look like a badass, have drama on social media"] * 3,
    'hate': ["Whoever just unfollowed me you a bitch"] * 3,
    'emotion': ["I love swimming for the same reason I love meditating...the feeling of weightlessness."] * 3,
    'emoji': ["Beautiful sunset last night from the pontoon @ Tupper Lake, New York"] * 3,
    "topic_classification": [
        'Jacob Collier is a Grammy-awarded English artist from London.',
        "I love swimming for the same reason I love meditating...the feeling of weightlessness.",
        "Beautiful sunset last night from the pontoon @ Tupper Lake, New York"
    ]
}


class Test(unittest.TestCase):
    """ Test """

    def test_model_mlm(self):
        model = tweetnlp.load_model('language_model')
        for best_n in [1, 5, 15]:
            out = model.predict(SAMPLE_MLM, best_n=best_n)
            assert len(out) == len(SAMPLE_MLM), f"{len(out)} != {len(SAMPLE_MLM)}"
            assert all(len(list(i.keys())) == 3 and 'best_tokens' in i.keys() for i in out), out
            assert all(len(list(i.keys())) == 3 and 'best_scores' in i.keys() for i in out), out
            assert all(len(list(i.keys())) == 3 and 'best_sentences' in i.keys() for i in out), out
            assert all(len(i['best_tokens']) == best_n for i in out), out
            assert all(len(i['best_scores']) == best_n for i in out), out
            assert all(len(i['best_sentences']) == best_n for i in out), out

            out = model.predict(SAMPLE_MLM, batch_size=2, best_n=best_n)
            assert len(out) == len(SAMPLE_MLM), f"{len(out)} != {len(SAMPLE_MLM)}"
            assert all(len(list(i.keys())) == 3 and 'best_tokens' in i.keys() for i in out), out
            assert all(len(list(i.keys())) == 3 and 'best_scores' in i.keys() for i in out), out
            assert all(len(list(i.keys())) == 3 and 'best_sentences' in i.keys() for i in out), out
            assert all(len(i['best_tokens']) == best_n for i in out), out
            assert all(len(i['best_scores']) == best_n for i in out), out
            assert all(len(i['best_sentences']) == best_n for i in out), out

            out = model.predict(SAMPLE_MLM[0], best_n=best_n)
            assert type(out) is dict, out
            assert len(list(out.keys())) == 3, out
            assert 'best_tokens' in out.keys(), out
            assert 'best_sentences' in out.keys(), out
            assert 'best_scores' in out.keys(), out
            assert len(out['best_tokens']) == best_n, out
            assert len(out['best_scores']) == best_n, out
            assert len(out['best_sentences']) == best_n, out

    def test_model_classification(self):
        for task, sample in SAMPLE_CLASSIFICATION.items():
            if task == 'topic_classification':
                models = [
                    tweetnlp.load_model(task, multi_label=True),
                    tweetnlp.load_model(task, multi_label=False)
                ]
            else:
                models = [tweetnlp.load_model(task)]

            for model in models:
                # batch prediction
                out = model.predict(sample)
                assert len(out) == len(sample), f"{len(out)} != {len(sample)}"
                assert all(len(list(i.keys())) == 1 and 'label' in i.keys() for i in out), out
                # batch prediction (define batch size)
                out = model.predict(sample, batch_size=2)
                assert len(out) == len(sample), f"{len(out)} != {len(sample)}"
                assert all(len(list(i.keys())) == 1 and 'label' in i.keys() for i in out), out
                # single prediction
                out = model.predict(sample[0])
                assert type(out) is dict, out
                assert len(list(out.keys())) == 1 and 'label' in out.keys(), out
                # prediction with probability
                out = model.predict(sample, return_probability=True)
                assert len(out) == len(sample), f"{len(out)} != {len(sample)}"
                assert all(len(i.keys()) == 2 for i in out), out
                assert all('probability' in i for i in out), out
                assert all('label' in i for i in out), out
                # prediction with probability (define batch)
                out = model.predict(sample, batch_size=2, return_probability=True)
                assert len(out) == len(sample), f"{len(out)} != {len(sample)}"
                assert all(len(i.keys()) == 2 for i in out), out
                assert all('probability' in i for i in out), out
                assert all('label' in i for i in out), out
                out = model.predict(sample[0], return_probability=True)
                assert type(out) is dict, out
                assert len(list(out.keys())) == 2 and 'label' in out.keys() and "probability" in out.keys(), out


if __name__ == "__main__":
    unittest.main()