import hashlib
import os
import pickle

from lark import Lark

CHUNK_SIZE = 65535
HASHER = hashlib.blake2b()

def hash_of_file(filename, hasher):
    with open(filename, 'rb') as f:
        while chunk := f.read(CHUNK_SIZE):
            hasher.update(chunk)

    return hasher.digest()

def _open_from_cache(filename, **kwargs):
    saved_hash = None
    try:
        with open(f'{filename}.pickle', 'rb') as saved_file:
            saved_hash = pickle.load(saved_file)
    except:
        pass

    if hash_of_file(filename, HASHER) != saved_hash:
        return _load_new(filename, **kwargs)
    else:
        return _load_from_cache(filename, **kwargs)

def _load_from_cache(filename, **kwargs):
    with open(f'{filename}.pickle', 'rb') as saved_file:
        _ = pickle.load(saved_file)
        return Lark.load(saved_file, **kwargs)

def _load_new(filename, **kwargs):
    with open(f'{filename}.pickle', 'wb') as saved_file:
        p = Lark.open(filename, **kwargs)
        pickle.dump(hash_of_file(filename, HASHER), saved_file)
        p.save(saved_file)

def load(filename, no_cache=False, **kwargs):
    saved_filename = f'{filename}.pickle'
    if os.path.exists(saved_filename) and not no_cache:
        return _open_from_cache(filename, **kwargs)
    else:
        return _load_new(filename, **kwargs)
