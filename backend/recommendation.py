import pandas as pd
import numpy as np
from scipy.stats import gaussian_kde
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import MinMaxScaler
from typing import List


def recommend_dishes_kde_enhanced(
    dishes_liked: List[str],
    df: pd.DataFrame,
    total_recommendations: int = 10,
    wildcard_ratio: float = 0.2,
    bandwidth: float = 0.1
) -> pd.DataFrame:
    """
    Recommend dishes by segmenting flavor vectors into clusters, then combining density, similarity,
    and distance metrics to rank items within each cluster.

    This function addresses the challenge of merely averaging a user's liked dishes. Instead, it:
      1. Identifies which flavor clusters the user likes most, based on K-Means cluster assignments.
      2. Computes a local density (via Gaussian KDE) around the cluster average flavor profile.
      3. Calculates a combined score = (density + similarity - distance) for each dish
         in those liked clusters.
      4. Selects dishes in proportion to how strongly the user prefers each cluster,
         while including a percentage of "wildcard" picks to introduce variety.

    Steps:
      1. Filter for the user's liked dishes (by `dish_name_clean_fuzzy`).
      2. Count how many liked dishes fall into each cluster to form a preference ratio.
      3. For each cluster with liked dishes:
         a. Compute the cluster's average flavor profile (mean of salty, bitter, sweet, sour, umami).
         b. Calculate cosine similarity between each dish in that cluster and the average profile.
         c. Compute a density measure (Gaussian KDE) if the cluster is large enough, otherwise
            fallback to similarity as a stand-in for density.
         d. Scale flavor vectors, compute Euclidean distance from the average profile, and build
            a combined score = density + similarity - distance.
         e. Rank dishes by combined score, then split into "regular" picks and "wildcard" picks,
            according to user preference for that cluster and the given `wildcard_ratio`.
      4. Aggregate picks from all clusters, globally sort by combined score, and return the
         top `total_recommendations`.

    Parameters
    ----------
    dishes_liked : list of str
        The list of dishes (identified by `dish_name_clean_fuzzy`) that the user has liked.
    df : pandas.DataFrame
        DataFrame containing at least the columns:
          - 'dish_name_clean_fuzzy': dish identifiers (strings)
          - 'Cluster': integer cluster assignment
          - 'salty', 'bitter', 'sweet', 'sour', 'umami': numeric flavor dimensions
        Typically includes all dishes plus their K-Means cluster labels.
    total_recommendations : int, default=10
        The total number of dishes to recommend.
    wildcard_ratio : float, default=0.2
        Fraction of dishes within each cluster pick that should be "wildcards," i.e. items slightly
        lower on the ranking to add variety.
    bandwidth : float, default=0.1
        Bandwidth parameter for the Gaussian KDE. Smaller values place a tighter emphasis on
        the local density.
    """

    liked_df = df[df["dish_name_clean_fuzzy"].isin(dishes_liked)]

    # Determine the frequency of clusters in the liked dishes
    cluster_counts = liked_df["Cluster"].value_counts()
    cluster_preferences = (
        cluster_counts / cluster_counts.sum()
    )  # Normalize cluster counts to get preferences

    # Recommendations DataFrame
    all_top = pd.DataFrame()

    # Process each cluster containing liked dishes
    for cluster, preference in cluster_preferences.items():
        cluster_data = df[df["Cluster"] == cluster]

        avg_profile = (
            cluster_data[["salty", "bitter", "sweet", "sour", "umami"]]
            .mean()
            .values.reshape(1, -1)
        )

        # Extract flavor data for the cluster
        flavor_data = cluster_data[["salty", "bitter", "sweet", "sour", "umami"]].values

        # Calculate cosine similarity and density
        cluster_data["similarity"] = cosine_similarity(
            flavor_data, avg_profile
        ).flatten()
        if len(cluster_data) > len(flavor_data[0]):
            kde = gaussian_kde(flavor_data.T, bw_method=bandwidth)
            densities = kde(flavor_data.T)
            cluster_data["density"] = densities
        else:
            cluster_data["density"] = cluster_data[
                "similarity"
            ]  # Use similarity as density if not enough data

        # Calculate Euclidean distance from the average profile
        scaler = MinMaxScaler()
        scaled_flavor_data = scaler.fit_transform(flavor_data)
        scaled_avg_profile = scaler.transform(avg_profile)
        cluster_data["distance"] = np.linalg.norm(
            scaled_flavor_data - scaled_avg_profile, axis=1
        )

        # Combine density and similarity into a single metric
        cluster_data["combined_score"] = (
            cluster_data["density"]
            + cluster_data["similarity"]
            - cluster_data["distance"]
        )

        # Select top recommendations based on the combined score
        sorted_recommendations = cluster_data.sort_values(
            by="combined_score", ascending=False
        )
        num_regular = int((1 - wildcard_ratio) * preference * total_recommendations)
        num_wildcards = int(wildcard_ratio * preference * total_recommendations)

        regular_recommendations = sorted_recommendations.head(num_regular)
        wildcard_recommendations = sorted_recommendations.iloc[
            num_regular : num_regular + num_wildcards
        ]

        # Gather all top recommendations
        final_selection = pd.concat([regular_recommendations, wildcard_recommendations])
        all_top = pd.concat([all_top, final_selection])

    # Ensure the total does not exceed the intended count
    all_top = all_top.sort_values(by="combined_score", ascending=False).head(
        total_recommendations
    )

    return all_top