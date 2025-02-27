from datasets import load_dataset
import uuid
from collections import OrderedDict

dataset = load_dataset('csv', data_files='src/news_articles.csv')

def add_uuid(example):
    # Generate a UUID using uuid5 with the URL namespace
    example['uuid'] = str(uuid.uuid5(uuid.NAMESPACE_URL, example['url']))
    return example

dataset = dataset.map(add_uuid)

def reorder_columns(example):
    return OrderedDict([
        ('uuid', example['uuid']),
        ('title', example['title']),
        ('author', example['author']),
        ('source', example['source']),
        ('url', example['url']),
        ('date', example['date']),
        ('content', example['content']),
    ])

dataset = dataset.map(reorder_columns)

print(dataset)

uuids = dataset["train"]["uuid"]

# dataset.push_to_hub("VaibhavSahai/news_articles")