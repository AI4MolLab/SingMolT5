import warnings
import sys
import os
import contextlib
from rdkit import Chem
from rdkit.Chem import MACCSkeys, RDKFingerprint, AllChem
from rdkit.DataStructs import TanimotoSimilarity
from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
import Levenshtein
import numpy as np
import pandas as pd
from tqdm import tqdm

# --- Suppress Warnings ---
warnings.filterwarnings("ignore", category=DeprecationWarning)
@contextlib.contextmanager
def suppress_rdkit_warnings():
    with open(os.devnull, 'w') as fnull:
        stderr = sys.stderr
        sys.stderr = fnull
        try:
            yield
        finally:
            sys.stderr = stderr

# Define evaluation functions
# --- BLEU Smoother ---
smoothie = SmoothingFunction().method1

# --- Metric Calculation Functions ---
def bleu_score(reference, candidate):
    return sentence_bleu([reference], candidate, smoothing_function=smoothie)

def levenshtein_Similarity(true_smiles, generated_smiles):
    
    lev_dist = Levenshtein.distance(true_smiles, generated_smiles)
    # Normalized Levenshtein Similarity
    max_len = max(len(true_smiles), len(generated_smiles))
    if max_len == 0:
        similarity = 1.0  # Both are empty strings, consider as a perfect match
    else:
        similarity = 1 - lev_dist / max_len
    return similarity

def maccs_similarity(smiles1, smiles2):
    mol1 = Chem.MolFromSmiles(smiles1)
    mol2 = Chem.MolFromSmiles(smiles2)
    fp1 = MACCSkeys.GenMACCSKeys(mol1)
    fp2 = MACCSkeys.GenMACCSKeys(mol2)
    return TanimotoSimilarity(fp1, fp2)

def rdk_similarity(smiles1, smiles2):
    mol1 = Chem.MolFromSmiles(smiles1)
    mol2 = Chem.MolFromSmiles(smiles2)
    fp1 = RDKFingerprint(mol1)
    fp2 = RDKFingerprint(mol2)
    return TanimotoSimilarity(fp1, fp2)

def morgan_similarity(smiles1, smiles2, radius=2, nBits=2048):
    mol1 = Chem.MolFromSmiles(smiles1)
    mol2 = Chem.MolFromSmiles(smiles2)
    fp1 = AllChem.GetMorganFingerprintAsBitVect(mol1, radius, nBits)
    fp2 = AllChem.GetMorganFingerprintAsBitVect(mol2, radius, nBits)
    return TanimotoSimilarity(fp1, fp2)

def check_validity(smiles):
    return int(Chem.MolFromSmiles(smiles) is not None)

# --- Batch Evaluation ---
def evaluate_batch(true_smiles_list, generated_smiles_list):
    results = {
        "BLEU": [],
        "Levenshtein Similarity": [],
        "MACCS FTS": [],
        "RDK FTS": [],
        "Morgan FTS": [],
        "Validity": []
    }

    for true_smiles, generated_smiles in zip(true_smiles_list, generated_smiles_list):
        valid = check_validity(generated_smiles)
        results["Validity"].append(valid)

        # BLEU, Exact Match, Levenshtein do not depend on structural validity
        results["BLEU"].append(bleu_score(list(true_smiles), list(generated_smiles)))
        results["Levenshtein Similarity"].append(levenshtein_Similarity(true_smiles, generated_smiles))

        if valid:
            results["MACCS FTS"].append(maccs_similarity(true_smiles, generated_smiles))
            results["RDK FTS"].append(rdk_similarity(true_smiles, generated_smiles))
            results["Morgan FTS"].append(morgan_similarity(true_smiles, generated_smiles))
        else:
            results["MACCS FTS"].append(np.nan)
            results["RDK FTS"].append(np.nan)
            results["Morgan FTS"].append(np.nan)

    return results

# --- Output Average Results (result_output) ---
def result_output(evaluation_results):
    print("\n=== Evaluation Results (Average over Batch) ===")
    for key, values in evaluation_results.items():
        if not values:
            print(f"{key:22s}: This metric list is empty, requires confirmation")

        # Check if values contain NaN
        contains_nan = False
        for v in values:
            if isinstance(v, float) and np.isnan(v):
                contains_nan = True
                break

        if contains_nan:
            values = np.nan_to_num(values, nan=0.0)  # Replace NaN with 0
            
        mean_val = np.mean(values)  # Calculate mean
        print(f"{key:22s}: {mean_val:.4f}")