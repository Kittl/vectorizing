import numpy as np
from faiss import Kmeans
from misc.imgutils import get_pixel_count, get_channel_count

def k_means_cluster(img, nclusters, nredo = 3):
    channel_count = img.shape[2]
    data = img.reshape(-1, channel_count).astype(np.float32)

    kmeans = Kmeans(
        channel_count,
        nclusters,
        niter = 100,
        nredo = nredo,
        int_centroids=True
    )

    kmeans.train(data)
    centers = kmeans.centroids.astype(np.uint8)
    _, labels = kmeans.index.search(data, 1)
    labels = np.reshape(labels, img.shape[:2]).astype(np.uint8)
    return labels, centers

def quick_silhouette_score(img, labels, centers):
    img = img.astype(np.int16)
    mapped = centers[labels].astype(np.int16)
    channel_count = get_channel_count(img)
    
    center_stack = []
    center_count = len(centers)
    infinity = np.full((channel_count,), np.inf)

    for x in range(center_count):
        mapped_equals_center = (mapped == centers[x]).all(axis = 2)
        center_entry = np.full([*mapped_equals_center.shape, channel_count], centers[x]).astype(np.float64)
        center_entry[mapped_equals_center] = infinity
        center_stack.append(center_entry)

    center_stack = np.stack(center_stack)
    mapped_stack = np.array([mapped] * center_count)
    stack_dist = np.linalg.norm(center_stack - mapped_stack, axis = 3)
    
    simmilarity = np.linalg.norm(img - mapped, axis = 2)
    dissimilarity = np.min(stack_dist, axis=0)

    pixel_count = get_pixel_count(img)
    sil = (dissimilarity - simmilarity) / np.maximum(simmilarity, dissimilarity)
    return np.sum(sil) / pixel_count

def optimal_kmeans(img, max_color_count, threshold = 0.85):
    res = None
    optimal_k = None

    max_score = -np.inf
    for k in range(6, 7):
        labels, centers = k_means_cluster(img, k)

        score = quick_silhouette_score(
            img, 
            labels,
            centers
        )

        if score > max_score:
            optimal_k = k
            max_score = score
            res = [labels, centers]
    
    labels, centers = res
    return optimal_k, labels, centers