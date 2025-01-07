# Cheshire Cat plugin to remove headers and footers ingesting documents

This plugin helps in the ingestion of documents with repetitive headers and footers, like usually are corporate documents, managing fuzzy matching to allow for small differences (e.g. page numbers)

### Settings

- **max_lines**: `int`
    - Maximum number of lines to look at for header/footer detection.

- **repeat_threshold**: `float (0-1)`
    - Minimum proportion of documents that a header/footer sequence must appear in to be considered. For example, 50% means that a sequence of lines is probably a header or footer if it is present in at least half of the pages of the document.

- **max_differences**: `int`
    - Maximum number of character differences allowed for a fuzzy match. (3 is okay for documents below 1000 pages.)

- **pdf_parser**: `PDFMinerParser | PDFPlumberParser`
    - Parser for PDF files.
        - `PDFMinerParser`: Default for the Cheshire Cat, usually good and especially good for arXiv papers with two columns per page.
        - `PDFPlumberParser`: Good for linear documents with tables - table rows are preserved as paragraphs.

- **debug_mode**: `bool`
    - When true, some files are stored in the plugin folder:
        - `docs.txt`: The LangChain Document list generated after document parsing.
        - `docs.pkl`: The serialized version of the Document list, used for experimenting with LangChain.
        - `docs_updated.txt`: The updated Document list with headers/footers removed.
        - `chunks`: The Document list generated after document split.

![Header Footer Cutting Cat](logo.png)