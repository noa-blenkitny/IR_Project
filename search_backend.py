import math
import numpy as np
from contextlib import closing #we use it for read posting list
import pickle
import re
from collections import OrderedDict, Counter, defaultdict
import hashlib
from heapq import heappop, heappush, heapify
from inverted_index_gcp import MultiFileReader
from inverted_index_gcp import MultiFileWriter
from inverted_index_gcp import InvertedIndex
import nltk
from nltk.stem.porter import *
from nltk.corpus import stopwords

english_stopwords = frozenset({'y', 'our', "that'll", 'after', 'out', 'her', 'he', 'other', 'was', 'whom', 'myself', 'its', 'is', 'over', 'shouldn', 'isn', 'will', 'same', "hasn't", 'his', 'on', 'of', 'hadn', 'being', 'here', 'be', 'each', 'don', 'the', 'through', "you've", 'by', 'all', 'to', 'how', 'should', 'than', 'having', 'll', 'it', 'are', 'who', 'into', 'mightn', 'me', 'i', 'ourselves', 'at', 'itself', 'my', 'only', 'before', 'she', 'where', 'few', "should've", 'because', 'which', 'yourself', 'about', 'more', "you're", "won't", 'does', 'during', 'if', 'but', 'what', 'has', "shouldn't", 'nor', 'any', 'd', "wouldn't", "couldn't", 'didn', "shan't", 'between', 'with', 're', 'yours', 'you', 'and', 'up', 'below', 've', 'they', 'ours', 'as', 'further', 'can', 'mustn', 'for', "she's", "haven't", 'once', 'these', 'there', 'ain', "you'd", "wasn't", 'such', "isn't", 'haven', 'won', 'm', 'ma', 'yourselves', "weren't", 'until', 'him', 'shan', 'wouldn', 'o', 'your', 'own', 'so', 'wasn', 'no', 'just', 'them', 'did', "doesn't", 'their', 'why', 'both', 'needn', 'we', 'that', 'am', 'then', 'some', "hadn't", "mustn't", 'this', "didn't", 'again', 'from', 'himself', 'under', 'in', 'not', "mightn't", 'or', 'down', 'themselves', 'have', "aren't", "needn't", 'doesn', 'herself', 'been', 'while', 'those', 'most', "it's", 'a', 'couldn', 'when', "don't", 'above', 'aren', 'hers', 'theirs', 't', 'off', 's', 'very', "you'll", 'were', 'now', 'too', 'weren', 'doing', 'had', 'do', 'against', 'an', 'hasn'})
corpus_stopwords = ["category", "references", "also", "external", "links", 
                    "may", "first", "see", "history", "people", "one", "two", 
                    "part", "thumb", "including", "second", "following", 
                    "many", "however", "would", "became"]
all_stopwords = english_stopwords.union(corpus_stopwords)
best_all_stopwords= all_stopwords.union(frozenset({"redirect","user"}))

RE_WORD = re.compile(r"""[\#\@\w](['\-]?\w){2,24}""", re.UNICODE)

#############helper func###########
def best_process_query(query):
  """Process the query and returns it after tokenizing and removal of stopwords- with additional words 

    Parameters:
    query (string): the query as "word1+word2"

    Returns:
    list:the query as list of tokens after tokenizer and removing stopwords

   """
  
  tokens = [token.group() for token in RE_WORD.finditer(query.lower())]
  tokens = [token for token in tokens if token not in best_all_stopwords ]
  return tokens

def process_query(query):
    

  """Process the query and returns it after tokenizing and removal of stopwords- as is in hw3

    Parameters:
    query (string): the query as "word1+word2"

    Returns:
    list:the query as list of tokens after tokenizer and removing stopwords

   """
  
  tokens = [token.group() for token in RE_WORD.finditer(query.lower())]
  tokens = [token for token in tokens if token not in all_stopwords ]
  return tokens

def get_candidate_doc_for_body(processed_query,index,query_score): 
  """returns the docs that are relevant to the query and need to calc cosSim with them

    Parameters:
    processed_query (list of strings): list of tokens of the query
    Returns:
    dict:the relevant docs for the query as {doc_id:numerator of cosSim}
    None: if no words of the query are in the corpus

   """
  candidate_docs_id={}
  for term in np.unique(processed_query):
    try: #if term in words:
      posting_list = read_posting_list(index,term)
      for docid,tf in posting_list:
        weight = ((tf/index.weights[docid][0])* math.log(index.N/index.df[term]))*query_score[term] 
        candidate_docs_id[docid] = candidate_docs_id.get(docid,0) + weight

    except(KeyError): #term is not in the corpus
      continue

  return candidate_docs_id #if there are no words at all returns none!

def get_candidate_doc_for_title_and_anchor(processed_query,index): 
  """returns the docs that are relevant to the query and their score
    Parameters:
    processed_query (list of strings): list of tokens of the query
    Returns:
    dict:the relevant docs for the query as {doc_id:score}
    None: if no words of the query are in the corpus

  """
  candidate_docs_id={}
  for term in np.unique(processed_query):
    try: #if term in words:
      posting_list = read_posting_list(index,term)
      for docid,tf in posting_list:   
        candidate_docs_id[docid] = candidate_docs_id.get(docid,0) + 1

    except(KeyError): #term is not in the corpus
      continue

  return candidate_docs_id #if there are no words at all returns none!

def cacl_tf_idf_query(processed_query,index):
    query_score = {}
    #calculating the tf of query tokens
    query_tf = Counter(processed_query)
    for term in np.unique(processed_query):
        #calculating wiq of query token
        try:
          query_score[term] = (query_tf[term]/len(processed_query)) * math.log(index.N/index.df[term])
        except(KeyError): #term is not in the corpus
            continue
    return query_score

def calc_cosSim(candidate_docs,index,query_score):
    """returns the cosSim scores of the candidate_docs

    Parameters:
    candidate_docs (dict): dict of {doc_id:numerator of cosSim}
    query_score (dict): dict of {query_token:tfidf weight}
    Returns:
    dict:the relevant docs for the query as {doc_id:cosSim}
   """
    scores={}
    for doc_id in candidate_docs:
      #scores[doc_id] =candidate_docs[doc_id]/(math.sqrt(index.weights[doc_id][1]*len(processed_query)))
      scores[doc_id] =candidate_docs[doc_id]/(math.sqrt(index.weights[doc_id][1]*sum([math.pow(score,2) for score in query_score.values()])))
    return scores

#posting list by word- could be useful when doing calculation dynamically in relation to the words in the query
TUPLE_SIZE = 6       
TF_MASK = 2 ** 16 - 1 # Masking the 16 low bits of an integer

def read_posting_list(inverted, w):
  with closing(MultiFileReader()) as reader:
    locs = inverted.posting_locs[w]
    b = reader.read(locs, inverted.df[w] * TUPLE_SIZE)
    posting_list = []
    for i in range(inverted.df[w]):
      doc_id = int.from_bytes(b[i*TUPLE_SIZE:i*TUPLE_SIZE+4], 'big')
      tf = int.from_bytes(b[i*TUPLE_SIZE+4:(i+1)*TUPLE_SIZE], 'big')
      posting_list.append((doc_id, tf))
    return posting_list

#########search func##############
def backend_search_body(query, index):
  """returns the docs that are relevant to the query as [(doc_id,score),(doc_id2,score)....] sorted by cosSim score in descending order

    Parameters:
    query (string): the query as "word1+word2"
    index (invertedIndex): the index you want to search in
    Returns:
    list of tuples :[(doc_id,score),(doc_id2,score)....] sorted by cosSim score in descending order

  """
  processed_query = process_query(query)
  query_score = cacl_tf_idf_query(processed_query,index)
  if len(query_score) == 0:
    return []
  candidate_docs = get_candidate_doc_for_body(processed_query,index,query_score)
  if candidate_docs == None: #there are no words in the query that are also in corpus
    return []

  scores_dict =calc_cosSim(candidate_docs,index,query_score)
  res=[]
  heap = []
  heapify(heap)
  for key, val in scores_dict.items():
      heappush(heap,(-1*val,key))
  counter=0
  while(heap and counter < 100):
    score,doc_id = heappop(heap)
    res.append((doc_id,score*-1))
    counter+=1
  return res

# will use it in the frontend_serch. returns the list of tuples [(doc_id,score)]    
def backend_search_title_anchor(query, index):
  """returns the docs that are relevant to the query as [(doc_id,score),(doc_id2,score)....] sorted by score in descending order

    Parameters:
    query (string): the query as "word1+word2"
    index (invertedIndex): the index you want to search in
    Returns:
    list of tuples :[(doc_id,score),(doc_id2,score)....] sorted by score in descending order

  """
  processed_query = process_query(query)
  scores_dict = get_candidate_doc_for_title_and_anchor(processed_query,index)
  if scores_dict == None: #there are no words in the query that are also in corpus
    return []
  res=[]
  heap = []
  heapify(heap)
  for key, val in scores_dict.items():
      heappush(heap,(-1*val,key))
  while(heap):
    score,doc_id = heappop(heap)
    res.append((doc_id,score*-1))
  return res

def backend_get_page_rank(page_rank_dict, list_of_pages):
  res = []
  for page in list_of_pages:
    try:
        res.append(page_rank_dict[page]) 
    except KeyError:
        res.append(0.0)
  return res

def backend_get_page_views(page_views_dict, list_of_pages):
  res = []
  for page in list_of_pages:
    try:
        res.append(page_views_dict[page]) 
    except KeyError:
        res.append(0)
  return res

def calc_idf_query(query, index):
  """
    This function calculate the idf values according to the BM25 idf formula for each term in the query.
    
    Parameters:
    -----------
    query: list of token representing the query. For example: ['look', 'blue', 'sky']
    
    Returns:
    -----------
    idf: dictionary of idf scores. As follows: 
                                                key: term
                                                value: bm25 idf score
  """
  idf = {}
  for token in np.unique(query):
    N = index.N
    n =  index.df.get(token,0)
    idf[token] = math.log(((N - n + 0.5)/( n + 0.5)) + 1)
  return idf

def get_candidate_doc_for_bm2_body(processed_query,index,query_idf): 
  """returns the docs that are relevant to the query and their bm25 scores

    Parameters:
    processed_query (list of strings): list of tokens of the query
    index (InvertedIndex): the index you want to search on
    query_idf: dict of {q_term:idf}
    Returns:
    dict:the relevant docs for the query as {doc_id:bm25}
    None: if no words of the query are in the corpus

   """
  candidate_docs_id={}
  for term in np.unique(processed_query):
    try: #if term in words:
      posting_list = read_posting_list(index,term)
      for docid,tf in posting_list:
        weight = query_idf[term]* (tf *(1.5+1))/(tf+index.weights[docid])
        candidate_docs_id[docid] = candidate_docs_id.get(docid,0) + weight
    except(KeyError): #term is not in the corpus
      continue
  return candidate_docs_id #if there are no words at all returns none!  

def best_backend_search(processed_query, index):
  """returns the docs that are relevant to the query as [(doc_id,score),(doc_id2,score)....] sorted by bm25 score in descending order

    Parameters:
    processed_query (list of strings): the query after tokenizing and removing stopwords
    index (invertedIndex): the index you want to search in
    Returns:
    list of tuples :[(doc_id,score),(doc_id2,score)....] sorted by bm25 score in descending order

  """
  query_idf = calc_idf_query(processed_query, index)
  candidate_docs = get_candidate_doc_for_bm2_body(processed_query,index,query_idf)
  if candidate_docs == None: #there are no words in the query that are also in corpus
    return []
  res=[]
  heap = []
  heapify(heap)
  for key, val in candidate_docs.items():
      heappush(heap,(-1*val,key))
  counter=0
  while(heap and counter < 100):
    score,doc_id = heappop(heap)
    res.append((doc_id,score*-1))
    counter+=1
  return res

def backend_search(query,bm25_B,bm25_T, text_weight, title_weight):
  processed_query = best_process_query(query)
  body_scores = best_backend_search(processed_query,bm25_B)
  title_scores = best_backend_search(processed_query,bm25_T)
  merged_scores= defaultdict(float)
  for k,v in body_scores:
    merged_scores[k]+=v*text_weight
  for k,v in title_scores:
    merged_scores[k]+=v*title_weight
  res=[]
  heap = []
  heapify(heap)
  for key, val in merged_scores.items():
      heappush(heap,(-1*val,key))
  counter=0
  while(heap and counter < 100):
    score,doc_id = heappop(heap)
    res.append((doc_id,score*-1))
    counter+=1
  return res

