def flatten_geo(geo):
    for compound_path in geo:
        for path in compound_path:
            for x in range(len(path)):
                path[x] = path[x].flattened()