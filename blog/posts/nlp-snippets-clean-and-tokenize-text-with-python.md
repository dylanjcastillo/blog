---
title: "Clean and Tokenize Text With Python"
description: "The first step in a Machine Learning project is cleaning the data. In this article, you'll find 20 code snippets to clean and tokenize text data using Python."
date: "12/10/2020"
date-modified: last-modified
toc: true
toc-depth: 3
author:
  - name: Dylan Castillo
    url: https://dylancastillo.co
    affiliation: Iwana Labs
    affiliation-url: https://iwanalabs.com
citation: true
---

## Table of Contents

- [How to use](#how-to-use)
- [Code snippets](#code-snippets)
  - [Cleaning text](#cleaning-text)
    - [Lowercase text](#lowercase-text)
    - [Remove cases (useful for caseles matching)](#remove-cases-useful-for-caseless-matching-)
    - [Remove hyperlinks](#remove-hyperlinks)
    - [Remove <a> tags but keep its content](#remove-a-tags-but-keep-its-content)
    - [Remove HTML tags](#remove-all-html-tags-but-keep-their-contents)
    - [Remove extra spaces, tabs, and line breaks](#remove-extra-spaces-tabs-and-line-breaks)
    - [Remove punctuation](#remove-punctuation)
    - [Remove numbers](#remove-numbers)
    - [Remove digits](#remove-digits)
    - [Remove non-alphabetic characters](#remove-non-alphabetic-characters)
    - [Remove all special characters and punctuation](#remove-all-special-characters-and-punctuation)
    - [Remove stopwords from a list](#remove-stopwords-from-a-list)
    - [Remove short tokens](#remove-short-tokens)
    - [Transform emojis to characters](#transform-emojis-to-characters)
  - [NLTK](#nltk)
    - [Tokenize text using NLTK](#tokenize-text-using-nltk)
    - [Tokenize tweets using NLTK](#tokenize-tweets-using-nltk)
    - [Split text into sentences using NLTK](#split-text-into-sentences-using-nltk)
    - [Remove stopwords using NLTK](#remove-stopwords-using-nltk)
  - [spaCy](#spacy)
    - [Tokenize text using spaCy](#tokenize-text-using-spacy)
    - [Split text into sentences using spaCy](#split-text-into-sentences-using-spacy)
  - [Keras](#keras)
    - [Tokenize text using Keras](#tokenize-text-using-keras)

---

Every time I start a new project, I promise to save the most useful code snippets for the future, but I never do.

The old ways are too compelling. I end up copying code from old projects, looking for the same questions in Stack Overflow, or reviewing the same Kaggle notebooks for the hundredth time. At this point, I don't know how many times I've googled for a variant of "remove extra spaces in a string using Python."

So, finally, I've decided to compile snippets and small recipes for frequent tasks. I'm starting with Natural Language Processing (NLP) because I've been involved in several projects in that area in the last few years.

For now, I'm planning on compiling code snippets and recipes for the following tasks:

- Cleaning and tokenizing text (this article)
- [Clustering documents](https://dylancastillo.co/nlp-snippets-cluster-documents-using-word2vec/)
- [Classifying text](https://dylancastillo.co/text-classification-using-python-and-scikit-learn/)

This article contains 20 code snippets you can use to clean and tokenize text using Python. I'll continue adding new ones whenever I find something useful. They're based on a mix of  Stack Overflow answers, books, and my experience.

In the next section, you can see an example of how to use the code snippets. Then, you can check the snippets on your own and take the ones you need.

## How to use

I'd recommend you combine the snippets you need into a function. Then, you can use that function for pre-processing or tokenizing text. If you're using **pandas**, you can apply that function to a specific column using the `.map` method of pandas' `Series`.

Take a look at the example below:

```python
import re
import pandas as pd

from string import punctuation

df = pd.DataFrame({
    "text_col": [
        "This TEXT needs \t\t\tsome cleaning!!!...",
        "This text too!!...       ",
        "Yes, you got it right!\n This one too\n"
    ]
})

def preprocess_text(text):
    text = text.lower()  # Lowercase text
    text = re.sub(f"[{re.escape(punctuation)}]", "", text)  # Remove punctuation
    text = " ".join(text.split())  # Remove extra spaces, tabs, and new lines
    return text

df["text_col"].map(preprocess_text)
```

## Code snippets

Before testing the snippets, copy the following function at the top of your Python script or Jupyter notebook.

```python
def print_text(sample, clean):
    print(f"Before: {sample}")
    print(f"After: {clean}")

```

### Cleaning text

These are functions you can use to clean text using Python. Most of them just use Python's standard libraries like `re` or `string`.

#### Lowercase text

It's fairly common to [lowercase text for NLP tasks](https://nlp.stanford.edu/IR-book/html/htmledition/capitalizationcase-folding-1.html). Luckily, Python strings include a `.lower()` method that makes that easy for you. Here's how you use it:

```python
sample_text = "THIS TEXT WILL BE LOWERCASED. THIS WON'T: ßßß"
clean_text = sample_text.lower()
print_text(sample_text, clean_text)

# ----- Expected output -----
# Before: THIS TEXT WILL BE LOWERCASED. THIS WON'T: ßßß
# After: this text will be lowercased. this won't: ßßß

```

#### Remove cases (useful for caseless matching)

Case folding is a common approach for matching strings (especially in languages other than English). Python strings provide you with `.casefold()` for that. Here's how to use it:

```python
sample_text = "THIS TEXT WILL BE LOWERCASED. THIS too: ßßß"
clean_text = sample_text.casefold()
print_text(sample_text, clean_text)

# ----- Expected output -----
# Before: THIS TEXT WILL BE LOWERCASED. THIS too: ßßß
# After: this text will be lowercased. this too: ssssss

```

#### Remove hyperlinks

If you're web scrapping, you'll often deal with hyperlinks. It's possible that you'd like to remove those to analyze the text. The easiest way to do that is by using regular expressions.

Python's `re` library is handy for those cases. This is how you'd remove hyperlinks using it:

```python
import re

sample_text = "Some URLs: https://example.com http://example.io http://exam-ple.com More text"
clean_text = re.sub(r"https?://\S+", "", sample_text)
print_text(sample_text, clean_text)

# ----- Expected output -----
# Before: Some URLs: https://example.com http://example.io http://exam-ple.com More text
# After: Some URLs:    More text

```

#### Remove <a> tags but keep their content

Similar to the previous case, if you're doing web scrapping, you might often find dealing with tags. In some cases, such as `<a>`, you may want to remove the tag and its attributes but not its contents (e.g., the text it contains).

You can use Python's `re` for that. Here's how you'd remove the `<a>` tag and its attributes while keeping its content:

```python
import re

sample_text = "Here's <a href='https://example.com'> a tag</a>"
clean_text = re.sub(r"<a[^>]*>(.*?)</a>", r"\1", sample_text)
print_text(sample_text, clean_text)

# ----- Expected output -----
# Before: Here's <a href='https://example.com'> a tag</a>
# After: Here's  a tag

```

You can also use this snippet as a starting point to remove other types of tags.

#### Remove all HTML tags but keep their contents

If you're dealing with web pages and want to remove all the tags in a document, you can use a generalized version of the previous snippet. Here's how you remove all the HTML tags using Python's `re` library:

```python
import re

sample_text = """
<body>
<div> This is a sample text with <b>lots of tags</b> </div>
<br/>
</body>
"""
clean_text = re.sub(r"<.*?>", " ", sample_text)
print_text(sample_text, clean_text)

# ----- Expected output -----
# Before:
# <body>
# <div> This is a sample text with <b>lots of tags</b> </div>
# <br/>
# </body>

# After:

#  This is a sample text with lots of tags

```

#### Remove extra spaces, tabs, and line breaks

You might think that the best approach to remove extra spaces, tabs, and line breaks would depend on regular expressions. But it doesn't.

The best approach consists of using a clever combination two string methods: `.split()` and `.join()`. First, you apply the `.split()` method to the string you want to clean. It will split the string by any whitespace and output a list. Then, you apply the `.join()` method on a string with a single whitespace (" "), using as input the list you generated. This will put back together the string you split but use a single whitespace as separator.

Yes, I know it sounds a bit confusing. But, in reality, it's fairly simple. Here's how it looks in code:

```python
sample_text = "     \t\tA      text\t\t\t\n\n sample       "
clean_text = " ".join(sample_text.split())
print_text(sample_text, clean_text)

# ----- Expected output -----
# Before:      		A      text

#  sample
# After: A text sample

```

#### Remove punctuation

Many NLP applications won't work very well if you include punctuation. So it's common to remove them. The easiest approach consists in using the `string` and `re` standard libraries are as follows:

```python
import re
from string import punctuation

sample_text = "A lot of !!!! .... ,,,, ;;;;;;;?????"
clean_text = re.sub(f"[{re.escape(punctuation)}]", "", sample_text)
print_text(sample_text, clean_text)

# ----- Expected output -----
# Before: A lot of !!!! .... ,,,, ;;;;;;;?????
# After: A lot of

```

#### Remove numbers

In some cases, you might want to remove numbers from text, when you don't feel they're very informative. You can use a regular expression for that:

```python
import re

sample_text = "Remove these numbers: 1919191 2229292 11.233 22/22/22. But don't remove this one H2O"
clean_text = re.sub(r"\b[0-9]+\b\s*", "", sample_text)
print_text(sample_text, clean_text)

# ----- Expected output -----
# Before: Remove these numbers: 1919191 2229292 11.233 22/22/22. But don't remove this one H2O
# After: Remove these numbers: .//. But don't remove this one H2O

```

#### Remove digits

There are cases where you might want to remove digits instead of any number. For instance, when you want to remove numbers but not dates. Using a regular expression gets a bit trickier.

In those cases, you can use the `.isdigit()` method of strings:

```python
sample_text = "I want to keep this one: 10/10/20 but not this one 222333"
clean_text = " ".join([w for w in sample_text.split() if not w.isdigit()]) # Side effect: removes extra spaces
print_text(sample_text, clean_text)

# ----- Expected output -----
# Before: I want to keep this one: 10/10/20 but not this one 222333
# After: I want to keep this one: 10/10/20 but not this one

```

#### Remove non-alphabetic characters

Sometimes, you'd like to remove non-alphabetic characters like numbers or punctuation. The `.isalpha()` method of Python strings will come in handy in those cases.

Here's how you use it:

```python
sample_text = "Sample text with numbers 123455 and words !!!"
clean_text = " ".join([w for w in sample_text.split() if w.isalpha()]) # Side effect: removes extra spaces
print_text(sample_text, clean_text)

# ----- Expected output -----
# Before: Sample text with numbers 123455 and words !!!
# After: Sample text with numbers and words

```

#### Remove all special characters and punctuation

In cases where you want to remove all characters except letters and numbers, you can use a regular expression.

Here's a quick way to do it:

```python
import re

sample_text = "Sample text 123 !!!! Haha.... !!!! ##$$$%%%%"
clean_text = re.sub(r"[^A-Za-z0-9\s]+", "", sample_text)
print_text(sample_text, clean_text)

# ----- Expected output -----
# Before: Sample text 123 !!!! Haha.... !!!! ##$$$%%%%
# After: Sample text 123  Haha

```

#### Remove stopwords from a list

There's the case where you'd like to exclude words using a predefined list. A quick way to do it is by using **list comprehensions**. Here's one way to do it:

```python
stopwords = ["is", "a"]
sample_text = "this is a sample text"
tokens = sample_text.split()
clean_tokens = [t for t in tokens if not t in stopwords]
clean_text = " ".join(clean_tokens)
print_text(sample_text, clean_text)

# ----- Expected output -----
# Before: this is a sample text
# After: this sample text

```

#### Remove short tokens

In some cases, you may want to remove tokens with few characters. In this case, using **list comprehensions** will make it easy:

```python
sample_text = "this is a sample text. I'll remove the a"
tokens = sample_text.split()
clean_tokens = [t for t in tokens if len(t) > 1]
clean_text = " ".join(clean_tokens)
print_text(sample_text, clean_text)

# ----- Expected output -----
# Before: this is a sample text. I'll remove the a
# After: this is sample text. I'll remove the

```

#### Transform emojis into characters

If you're processing social media data, there might be cases where you'd like to extract the meaning of emojis instead of simply removing them. An easy way to do that is by using the [emoji](https://pypi.org/project/emoji/) library.

Here's how you do it:

```python
from emoji import demojize

sample_text = "I love 🥑"
clean_text = demojize(sample_text)
print_text(sample_text, clean_text)

# ----- Expected output -----
# Before: I love 🥑
# After: I love :avocado:

```

#### Remove repeated characters

In some cases, you may want to remove repeated characters, so instead of "helloooo" you use "hello". Here's how you can do it (I got this code snippet from [The Kaggle Book](https://www.amazon.com/Data-Analysis-Machine-Learning-Kaggle-ebook/dp/B09F3STL34)):

```python
import re

sample_text = "hellooooo"
clean_text = re.sub(r'(.)\1{3,}',r'\1', sample_text)
print_text(sample_text, clean_text)

# ----- Expected output -----
# Before: hellooooo
# After: hello
```

### NLTK

Before using NLTK's snippets, you need to install NLTK. You can do that as follows: `pip install nltk`.

#### Tokenize text using NLTK

```python
from nltk.tokenize import word_tokenize

sample_text = "this is a text ready to tokenize"
tokens = word_tokenize(sample_text)
print_text(sample_text, tokens)

# ----- Expected output -----
# Before: this is a text ready to tokenize
# After: ['this', 'is', 'a', 'text', 'ready', 'to', 'tokenize']

```

#### Tokenize tweets using NLTK

```python
from nltk.tokenize import TweetTokenizer

tweet_tokenizer = TweetTokenizer()
sample_text = "This is a tweet @jack #NLP"
tokens = tweet_tokenizer.tokenize(sample_text)
print_text(sample_text, tokens)

# ----- Expected output -----
# Before: This is a tweet @jack #NLP
# After: ['This', 'is', 'a', 'tweet', '@jack', '#NLP']

```

#### Split text into sentences using NLTK

```python
from nltk.tokenize import sent_tokenize

sample_text = "This is a sentence. This is another one!\nAnd this is the last one."
sentences = sent_tokenize(sample_text)
print_text(sample_text, sentences)

# ----- Expected output -----
# Before: This is a sentence. This is another one!
# And this is the last one.
# After: ['This is a sentence.', 'This is another one!', 'And this is the last one.']

```

### Remove stopwords using NLTK

```python
import nltk

from nltk.corpus import stopwords

nltk.download("stopwords")

stopwords_ = set(stopwords.words("english"))

sample_text = "this is a sample text"
tokens = sample_text.split()
clean_tokens = [t for t in tokens if not t in stopwords_]
clean_text = " ".join(clean_tokens)
print_text(sample_text, clean_text)

# ----- Expected output -----
# Before: this is a sample text
# After: sample text
```

### spaCy

Before using spaCy's snippets, you need to install the library as follows: `pip install spacy`. You also need to download a language model. For English, here's how you do it: `python -m spacy download en_core_web_sm`.

#### Tokenize text using spaCy

```python
import spacy

nlp = spacy.load("en_core_web_sm")

sample_text = "this is a text ready to tokenize"
doc = nlp(sample_text)
tokens = [token.text for token in doc]
print_text(sample_text, tokens)

# ----- Expected output -----
# Before: this is a text ready to tokenize
# After: ['this', 'is', 'a', 'text', 'ready', 'to', 'tokenize']

```

#### Split text into sentences using spaCy

```python
import spacy

nlp = spacy.load("en_core_web_sm")

sample_text = "This is a sentence. This is another one!\nAnd this is the last one."
doc = nlp(sample_text)
sentences = [sentence.text for sentence in doc.sents]
print_text(sample_text, sentences)

# ----- Expected output -----
# Before: This is a sentence. This is another one!
# And this is the last one.
# After: ['This is a sentence.', 'This is another one!\n', 'And this is the last one.']

```

### Keras

Before using Keras' snippets, you need to install the library as follows: `pip install tensorflow && pip install keras`.

#### Tokenize text using Keras

```python
from keras.preprocessing.text import text_to_word_sequence

sample_text = 'This is a text you want to tokenize using KERAS!!'
tokens = text_to_word_sequence(sample_text)
print_text(sample_text, tokens)

# ----- Expected output -----
# Before: This is a text you want to tokenize using KERAS!!
# After: ['this', 'is', 'a', 'text', 'you', 'want', 'to', 'tokenize', 'using', 'keras']
```
