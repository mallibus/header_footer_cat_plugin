import pickle
from typing import List
from collections import defaultdict
from copy import deepcopy
from pathlib import Path

from cat.mad_hatter.decorators import tool, hook
from cat.log import log

from langchain.docstore.document import Document
from langchain_community.document_loaders.parsers.pdf import PDFMinerParser, PDFPlumberParser

from thefuzz import fuzz 

from .settings import tmp_files_path

@hook
def rabbithole_instantiates_parsers(file_handlers: dict, cat) -> dict:
    """
    Hook to change the PDF parser used by RabbitHole for parsing PDF files.
    """
    settings = cat.mad_hatter.get_plugin().load_settings()
    if settings["pdf_parser"] == "PDFMinerParser":
       file_handlers["application/pdf"] = PDFMinerParser()
       log.info(f"PDF file handler for application/pdf changed to PDFMinerParser()")
    elif settings["pdf_parser"] == "PDFPlumberParser":
       file_handlers["application/pdf"] = PDFPlumberParser()
       log.info(f"PDF file handler for application/pdf changed to PDFPlumberParser()")
    
    return file_handlers

def write_documents_to_text_file(documents : List[Document], file_path : Path):
  """
  Writes a list of Document objects to a text file in a readable format.

  Args:
    documents: A list of Document objects.
    file_path: The path to the output text file.
  """
  
  log.info(f"Writing documents to text file: {file_path}")
  log.info(f"Making folder: {file_path.parent}")
  file_path.parent.mkdir(parents=False, exist_ok=True)

  with open(file_path, 'w') as f:
    f.write(f"List of {len(documents)} documents\n---------------------------------------------------------\n\n")
    for i,doc in enumerate(documents):
        f.write(f"Document {i}:\n\n")
        for attr, value in doc.__dict__.items():
            f.write(f"Attribute: {attr} Value: {value}\n")
        f.write(f"---------------------------------------------------------\n\n") 


def write_documents_to_pickle(documents, file_path):
  """
  Writes a list of Document objects to a pickle.

  Args:
    documents: A list of Document objects.
    file_path: The path to the output file.
  """
  log.info(f"Writing documents to pickle file: {file_path}")
  log.info(f"Making folder: {file_path.parent}")
  file_path.parent.mkdir(parents=False, exist_ok=True)

  with open(file_path, 'wb') as f:
    pickle.dump(documents, f)


def count_documents_with_similar_n_lines(documents : List[Document], max_lines=5, max_differences=3, header=True):
  """
  Counts the number of documents with similar strings in the first 
  or last n lines, allowing for minor variations using fuzzy matching.

  Args:
    documents: A list of Document objects.
    max_lines: The maximum number of lines to consider for comparison.

    max_differences: The maximum number of character differences allowed 
                     between sequences to be considered a match.
    from_top: If True, considers lines from the top (header); 
             if False, considers lines from the bottom (footer).

  Returns:
    A dictionary where keys are the unique strings found in the 
    specified region and values are the count of documents with that string.
  """
  counts = defaultdict(int)
  for doc in documents:
    lines = doc.page_content.splitlines()
    for n in range(1, max_lines + 1):  # Loop through different line counts
      if header:
        selected_lines = lines[:n] 
      else:
        selected_lines = lines[-n:]
      first_n_lines = "\n".join(selected_lines)

      # Find the most similar existing key 
      most_similar_key = None
      max_ratio = 0
      for key in counts:
        ratio = fuzz.ratio(first_n_lines, key)
        if ratio > max_ratio:
          max_ratio = ratio
          most_similar_key = key

      # If similarity exceeds threshold, increment the count of the most similar key
      if most_similar_key is not None and max_ratio >= 100 - (max_differences * 100 / len(first_n_lines)):
        counts[most_similar_key] += 1
      else:
        counts[first_n_lines] += 1
  return counts


def get_frequent_sequences(counts : dict, min_count_threshold=2):
    """
    Filters the dictionary and returns a list of sequences 
    that occur more than the specified minimum count.

    Args:
        counts: A dictionary where keys are sequences and values are their counts.
        min_count_threshold: The minimum count for a sequence to be included.

    Returns:
        A list of sequences that occur more than the minimum count.
    """
    frequent_sequences = [{'sequence':key,'count':count} for key, count in counts.items() if count >= min_count_threshold]
    frequent_sequences.sort(key=lambda x: len(x['sequence']), reverse=True)
    return frequent_sequences


def remove_sequence_from_documents(documents : List[Document], sequence : str, max_differences=3, cat = None):
  """
  Removes the given sequence from the beginning or end of the text 
  in each Document object using fuzzy matching.

  Args:
    documents: A list of Document objects.
    sequence: The sequence to be removed.
    max_differences: The maximum number of character differences 
                     allowed for a fuzzy match.

  Returns:
    A list of Document objects with the sequence removed.
  """
  cleaned_documents = []
  count_clean_head = 0
  count_clean_tail = 0
  for doc in documents:
    text = doc.page_content.strip()
    original_text = text 

    # Check for fuzzy match at the beginning
    if fuzz.ratio(sequence, text[:len(sequence)]) >= 100 - (max_differences * 100 / len(sequence)):
      text = text[len(sequence):].lstrip()
      count_clean_head += 1

    # Check for fuzzy match at the end
    if fuzz.ratio(sequence, text[-len(sequence):]) >= 100 - (max_differences * 100 / len(sequence)):
      text = text[:-len(sequence)].rstrip()
      count_clean_tail += 1

    cleaned_documents.append(Document(page_content=text, metadata=doc.metadata))

  if count_clean_head > 0 :
      message = f"removed {count_clean_head} headers strings {sequence}"
      log.info(message)
      cat.send_ws_message(message, msg_type="notification")
  if count_clean_tail > 0 :    
      message = f"removed {count_clean_tail} footers strings {sequence}"
      log.info(message)
      cat.send_ws_message(message, msg_type="notification")

  
  return cleaned_documents


def remove_headers_and_footers(docs:List[Document], 
                               max_lines:int, 
                               repeat_threshold:float, 
                               max_differences:int, 
                               cat ) -> List[Document]:
    """
      Removes common headers and footers from a list of Document objects.

      Args:
        docs: A list of Document objects.
        max_lines: The maximum number of lines to consider for header/footer detection.
        repeat_threshold: The minimum proportion of documents 
                          that a header/footer sequence must appear in to be considered.
    
      Returns:
        A new list of Document objects with identified headers and footers removed.
    
      This function:
        1. Identifies potential header and footer sequences using 
           `count_documents_with_similar_n_lines` function.
        2. Filters sequences based on the `repeat_threshold` 
           to ensure they appear in a significant portion of documents.
        3. Removes identified header and footer sequences from the 
           text of each Document object.
        4. Returns a new list of Document objects with headers and 
           footers removed.
    """
    # Find the minimum number of documents a sequence must appear in to be considered
    # lower limit of 2 to avoid removing full pages if there is only one page
    min_repeting_docs = max(2, len(docs) * repeat_threshold)

    header_counts = count_documents_with_similar_n_lines(docs, max_lines=max_lines, max_differences=max_differences, header=True)
    footer_counts = count_documents_with_similar_n_lines(docs, max_lines=max_lines, max_differences=max_differences, header=False)

    headers = get_frequent_sequences(header_counts,min_repeting_docs)
    footers = get_frequent_sequences(footer_counts,min_repeting_docs)
    
    docs_update = deepcopy(docs)
    for sequence in headers + footers:
        docs_update = remove_sequence_from_documents(docs_update,sequence['sequence'], cat=cat)

    return docs_update



@hook(priority=1)
def before_rabbithole_splits_text(docs: List[Document], cat) -> List[Document]:
    """
    Processes a list of documents by removing headers and footers before further text splitting.
    Args:
      docs (List[Document]): A list of Document objects to be processed.
      cat: the Cheshire cat session.
    Returns:
      List[Document]: A list of Document objects with headers and footers removed.
    """
    settings = cat.mad_hatter.get_plugin().load_settings()


    if settings["debug_mode"]:
        write_documents_to_text_file(docs, Path(tmp_files_path)/"docs.txt")
        write_documents_to_pickle(docs, Path(tmp_files_path)/"docs.pkl")


    max_lines = settings["max_lines"]
    repeat_threshold = settings["repeat_threshold"]
    max_differences = settings["max_differences"]
    docs_updated = remove_headers_and_footers(docs, max_lines, repeat_threshold, max_differences, cat)

    if settings["debug_mode"]:
       write_documents_to_text_file(docs_updated, Path(tmp_files_path)/"docs_updated.txt")

    return docs_updated


@hook(priority=1)
def after_rabbithole_splitted_text(chunks: List[Document], cat) -> List[Document]:
    """Hook the `Document` after is split.

    Allows editing the list of `Document` right after the *RabbitHole* chunked them in smaller ones.

    Parameters
    ----------
    chunks : List[Document]
        List of Langchain `Document`.
    cat : CheshireCat
        Cheshire Cat instance.

    Returns
    -------
    chunks : List[Document]
        List of modified chunked langchain documents to be stored in the episodic memory.

    """

    write_documents_to_text_file(chunks, Path(tmp_files_path)/"chunks.txt")

    return chunks