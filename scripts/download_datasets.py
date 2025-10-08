import urllib.request
import zipfile
import os

datasets = [
    {
        'name': 'spamassassin',
        'url': 'https://spamassassin.apache.org/old/publiccorpus/20050311_spam_2.tar.bz2',
        'type': 'spam'
    },
    {
        'name': 'spamassassin_ham',
        'url': 'https://spamassassin.apache.org/old/publiccorpus/20030228_easy_ham.tar.bz2',
        'type': 'ham'
    }
]

os.makedirs('data/raw', exist_ok=True)

for dataset in datasets:
    print(f"Downloading {dataset['name']}...")
    filename = f"data/raw/{dataset['name']}.tar.bz2"
    urllib.request.urlretrieve(dataset['url'], filename)
    print(f"✓ Downloaded {filename}")
