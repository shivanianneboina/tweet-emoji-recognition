""" Simple interface for CardiffNLP twitter models. """
# TODO: Add preprocessing to handle the twitter username
import logging
import csv
import json
import os
import re
import urllib.request
from typing import List, Dict

import torch
from urlextract import URLExtract
from transformers import AutoTokenizer, AutoModelForSequenceClassification, AutoConfig

URLEx = URLExtract()
DEFAULT_CACHE_DIR = f"{os.path.expanduser('~')}/.cache/tweetnlp/classification"
MODEL_LIST = {
    'emotion': {
        "default": "cardiffnlp/twitter-roberta-base-emotion"
    },
    'emoji': {
        "default": "cardiffnlp/twitter-roberta-base-emoji"
    },
    'hate': {
        "default": "cardiffnlp/twitter-roberta-base-hate"
    },
    'irony': {
        "default": "cardiffnlp/twitter-roberta-base-irony"
    },
    'offensive': {
        "default": "cardiffnlp/twitter-roberta-base-offensive"
    },
    'sentiment': {
        "default": "cardiffnlp/twitter-roberta-base-sentiment-latest",
        "multilingual": "cardiffnlp/twitter-xlm-roberta-base-sentiment",
    },
    'topic_classification': {
        "single_label": 'cardiffnlp/twitter-roberta-base-dec2021-tweet-topic-single-all',
        "multi_label": 'cardiffnlp/twitter-roberta-base-dec2021-tweet-topic-multi-all'
    }
}


def load_model(model, local_files_only: bool = False):
    config = AutoConfig.from_pretrained(model, local_files_only=local_files_only)
    tokenizer = AutoTokenizer.from_pretrained(model, local_files_only=local_files_only)
    model = AutoModelForSequenceClassification.from_pretrained(model, config=config, local_files_only=local_files_only)
    return config, tokenizer, model


def download_id2label(task):
    path = f'{DEFAULT_CACHE_DIR}/id2label/{task}'
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # download label mapping
        mapping_link = f"https://raw.githubusercontent.com/cardiffnlp/tweeteval/main/datasets/{task}/mapping.txt"
        with urllib.request.urlopen(mapping_link) as f:
            html = f.read().decode('utf-8').split("\n")
            csvreader = csv.reader(html, delimiter='\t')
        labels = [row[1] for row in csvreader if len(row) > 1]
        id2label = {str(n): _l for n, _l in enumerate(labels)}
        with open(path, 'w') as f:
            json.dump(id2label, f)
    else:
        with open(path) as f:
            id2label = json.load(f)
    return id2label


def preprocess(text):
    text = re.sub(r"@[A-Z,0-9]+", "@user", text)
    urls = URLEx.find_urls(text)
    for _url in urls:
        try:
            text = text.replace(_url, "http")
        except re.error:
            logging.warning(f're.error:\t - {text}\n\t - {_url}')
    return text


class Classifier:

    def __init__(self, model_name: str, max_length: int, id_to_label: Dict = None, multi_label: bool = False):
        try:
            self.config, self.tokenizer, self.model = load_model(model_name)
        except Exception:
            self.config, self.tokenizer, self.model = load_model(model_name, local_files_only=True)
        self.max_length = max_length
        self.multi_label = multi_label
        if id_to_label is None:
            self.id_to_label = {str(v): k for k, v in self.config.label2id.items()}
        else:
            self.id_to_label = id_to_label
        # GPU setup
        self.device = 'cuda' if torch.cuda.device_count() > 0 else 'cpu'
        self.parallel = torch.cuda.device_count() > 1
        if self.parallel:
            self.model = torch.nn.DataParallel(self.model)
        self.model.to(self.device)
        logging.debug(f'{torch.cuda.device_count()} GPUs are in use')

    def predict(self, text: str or List, batch_size: int = None, return_probability: bool = False):
        self.model.eval()
        single_input_flag = type(text) is str
        text = [text] if single_input_flag else text
        text = [preprocess(t) for t in text]
        batch_size = len(text) if batch_size is None else batch_size
        _index = list(range(0, len(text), batch_size)) + [len(text) + 1]
        probs = []
        with torch.no_grad():
            for i in range(len(_index) - 1):
                encoded_input = self.tokenizer.batch_encode_plus(
                    text[_index[i]: _index[i+1]],
                    max_length=self.max_length,
                    return_tensors='pt',
                    padding=True,
                    truncation=True)
                output = self.model(**{k: v.to(self.device) for k, v in encoded_input.items()})
                if self.multi_label:
                    probs += torch.sigmoid(output.logits).cpu().tolist()
                else:
                    probs += torch.softmax(output.logits, -1).cpu().tolist()

        if return_probability:
            if self.multi_label:
                out = [{
                    'label': [self.id_to_label[str(n)] for n, p in enumerate(_pr) if p > 0.5],
                    'probability': {self.id_to_label[str(n)]: p for n, p in enumerate(_pr)}
                } for _pr in probs]
            else:
                out = [{
                    'label': self.id_to_label[str(p.index(max(p)))],
                    'probability': {self.id_to_label[str(n)]: _p for n, _p in enumerate(p)}
                } for p in probs]
        else:
            if self.multi_label:
                out = [{'label': [self.id_to_label[str(n)] for n, p in enumerate(_pr) if p > 0.5]} for _pr in probs]
            else:
                out = [{'label': self.id_to_label[str(p.index(max(p)))]} for p in probs]
        if single_input_flag:
            return out[0]
        return out


class TopicClassification:

    def __init__(self, model: str = None, max_length: int = 128, multi_label: bool = True):
        if model is None:
            model = MODEL_LIST['topic_classification']['multi_label' if multi_label else 'single_label']
        self.model = Classifier(model, max_length, multi_label=multi_label)
        self.topic = self.predict = self.model.predict


class Sentiment:

    def __init__(self, model: str = None, max_length: int = 128, multilingual: bool = False):
        if model is None:
            model = MODEL_LIST['sentiment']['multilingual' if multilingual else 'default']
        self.model = Classifier(model, max_length, download_id2label('sentiment'))
        self.sentiment = self.predict = self.model.predict


class Offensive:

    def __init__(self, model: str = None, max_length: int = 128):
        if model is None:
            model = MODEL_LIST['offensive']['default']
        self.model = Classifier(model, max_length, download_id2label('offensive'))
        self.offensive = self.predict = self.model.predict


class Irony:

    def __init__(self, model: str = None, max_length: int = 128):
        if model is None:
            model = MODEL_LIST['irony']['default']
        self.model = Classifier(model, max_length, download_id2label('irony'))
        self.irony = self.predict = self.model.predict


class Hate:

    def __init__(self, model: str = None, max_length: int = 128):
        if model is None:
            model = MODEL_LIST['hate']['default']
        self.model = Classifier(model, max_length, download_id2label('hate'))
        self.hate = self.predict = self.model.predict


class Emotion:

    def __init__(self, model: str = None, max_length: int = 128):
        if model is None:
            model = MODEL_LIST['emotion']['default']
        self.model = Classifier(model, max_length, download_id2label('emotion'))
        self.emotion = self.predict = self.model.predict


class Emoji:

    def __init__(self, model: str = None, max_length: int = 128):
        if model is None:
            model = MODEL_LIST['emoji']['default']
        self.model = Classifier(model, max_length, download_id2label('emoji'))
        self.emoji = self.predict = self.model.predict


if __name__ == '__main__':
    _model = TopicClassification(multi_label=True)
    _model.predict(["this is a sample game", "we sell newspaper", "Beer Beer"])
    _model.predict(["this is a sample game", "we sell newspaper", "Beer Beer"], return_probability=True)

    _model = TopicClassification(multi_label=False)
    _model.predict(["this is a sample game", "we sell newspaper", "Beer Beer"])
    _model.predict(["this is a sample game", "we sell newspaper", "Beer Beer"], return_probability=True)