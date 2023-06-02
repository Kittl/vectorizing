import cv2
import numpy as np
from faiss import Kmeans
from skimage.measure import label
from scipy.ndimage import distance_transform_edt

def cluster(img, img_info, nclusters):
    dims = img_info.dims
    channel_count = img_info.channel_count

    data = np.reshape(img, (-1, channel_count)).astype(np.float32)
    kmeans = Kmeans(channel_count, nclusters)
    kmeans.train(data)
    
    _, labels = kmeans.index.search(data, 1)
    labels = np.reshape(labels, dims).astype(np.uint8)
    colors = kmeans.centroids.astype(np.uint8)
    return labels, colors

def cleanup(img_info, labels, centers):
    dims = img_info.dims

    labels = np.uint16(labels)
    labels = np.reshape(labels + 1, dims)
    color_count = len(centers)

    clusters = [np.where(labels == idx + 1, idx + 1, 0) for idx, _ in enumerate(centers)]
    cluster_islands = [label(cluster) for cluster in clusters]

    islands_count = 0
    for x in range(color_count):
        cluster_islands[x] = np.add(
            cluster_islands[x], 
            islands_count, 
            where = cluster_islands[x] != 0, 
            out = np.zeros(dims)
        )
        islands_count = cluster_islands[x].max()
    
    islands = np.zeros(dims).astype(np.uint32)
    for island in cluster_islands:
        islands = np.where(islands == 0, island, islands).astype(np.uint32)

    islands += 1
    islands_backup = np.array(islands, copy = True)
    
    kernel = np.ones((2, 2))
    island_areas = np.bincount(islands.flatten())

    for cluster in clusters:
        dilated_cluster = cv2.dilate(cluster.astype(np.uint8), kernel)
        dilated_outline = np.logical_xor(cluster, dilated_cluster)
        islands = np.where(dilated_outline == 1, 0, islands)

    island_areas_after = np.bincount(islands.flatten(), minlength=len(island_areas))
    island_areas_ratio = np.divide(
        np.float32(island_areas_after),
        np.float32(island_areas),
        out=np.zeros(island_areas.shape),
        where=island_areas != 0
    )

    mask_1 = np.where(island_areas_after[islands_backup] <= 16, 0, 1)
    mask_2 = np.where(island_areas_ratio[islands_backup] <= 0.2, 0, 1)
    mask = mask_1 & mask_2
    labels = np.where(mask == 1, labels, 0)

    closest = distance_transform_edt(np.logical_not(labels), return_distances = False, return_indices = True)
    labels = np.where(labels != 0, labels, labels[closest[0], closest[1]])
    return labels - 1, centers

def posterize(img, img_info, color_count):
    labels, colors = cluster(img, img_info, color_count)
    labels, colors = cleanup(img_info, labels, colors)
    return labels, colors