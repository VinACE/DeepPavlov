import json
import logging
from pathlib import Path
import unicodedata
import sqlite3
from typing import Union, List, Tuple, Generator, Any
from multiprocessing import Pool

from tqdm import tqdm

logger = logging.getLogger(__name__)


class ODQADataReader:

    @staticmethod
    def read(data_path, *args, **kwargs) -> None:
        logger.info('Reading files...')
        if kwargs['dataset_format'] == 'sqlite':
            return
        _build_db(kwargs['save_path'], kwargs['dataset_format'], data_path)


def iter_files(path: Union[Path, str]) -> Generator[Path, Any, Any]:
    path = Path(path)
    if path.is_file():
        yield path
    elif path.is_dir():
        for item in path.iterdir():
            yield from iter_files(item)
    else:
        raise RuntimeError("Path doesn't exist: {}".format(path))


def _build_db(save_path, dataset_format, data_path: Union[Path, str], num_workers=4):
    logger.info('Building the database...')
    conn = sqlite3.connect(str(save_path))
    c = conn.cursor()
    sql_table = "CREATE TABLE documents (id PRIMARY KEY, text);"
    c.execute(sql_table)

    files = [f for f in iter_files(data_path)]
    workers = Pool(num_workers)

    if dataset_format == 'txt':
        fn = _get_file_contents
    elif dataset_format == 'json':
        fn = _get_json_contents
    elif dataset_format == 'wiki':
        fn = _get_wiki_contents
    else:
        raise RuntimeError('Unknown dataset format.')

    with tqdm(total=len(files)) as pbar:
        for data in tqdm(workers.imap_unordered(fn, files)):
            c.executemany("INSERT INTO documents VALUES (?,?)", data)
            pbar.update()

    conn.commit()
    conn.close()


def _get_file_contents(fpath) -> List[Tuple[str, str]]:
    """
    Read a single txt file.
    :param fpath: path to a txt file
    :return: tuple of file names and contents
    """
    with open(fpath) as fin:
        text = fin.read()
        normalized_title = unicodedata.normalize('NFD', fpath.name)
        return [(normalized_title, text)]


def _get_json_contents(fpath) -> List[Tuple[str, str]]:
    """
    Read a single json file.
    :return: tuple of file names and contents
    """
    docs = []
    with open(fpath) as fin:
        for line in fin:
            data = json.loads(line)
            for doc in data:
                if not doc:
                    continue
                title = doc['title']
                normalized_title = unicodedata.normalize('NFD', str(title))
                text = doc['text']
                docs.append((normalized_title, text))
    return docs


def _get_wiki_contents(fpath) -> List[Tuple[str, str]]:
    """
    Read a single wikipedia-extractor formatted file.
    :param fpath: path to a wikipedia-formatted file
    :return: tuple of file names and contents
    """
    docs = []
    with open(fpath) as fin:
        for line in fin:
            doc = json.loads(line)
            if not doc:
                continue
            title = doc['title']
            normalized_title = unicodedata.normalize('NFD', str(title))
            text = doc['text']
            docs.append((normalized_title, text))
    return docs
