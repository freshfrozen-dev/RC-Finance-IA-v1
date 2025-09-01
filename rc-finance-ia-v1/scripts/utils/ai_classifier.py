from sentence_transformers import SentenceTransformer, util

# Lista de categorias base
CATEGORIES = [
    "moradia", "transporte", "alimentacao", "lazer", "educacao",
    "investimentos", "saude", "dividas", "fundo de emergencia"
]

model = SentenceTransformer('paraphrase-MiniLM-L6-v2')
category_embeddings = model.encode(CATEGORIES, convert_to_tensor=True)

def classify_transaction(description):
    description_embedding = model.encode(description, convert_to_tensor=True)
    similarity = util.cos_sim(description_embedding, category_embeddings)[0]
    best_idx = similarity.argmax().item()
    return CATEGORIES[best_idx]