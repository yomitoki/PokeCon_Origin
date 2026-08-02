# LocalFunction

This folder contains portable extensions used by Dev Studio generated commands.
It does not replace or patch PokeCon's original command classes.

For an image-detection command, distribute the generated command, its template
images and `LocalFunction/ImageDetection.py`. `SimilarityHistory`,
`render_similarity_graph()` and `compose_monitor_frame()` are the common layer
for future continuous similarity logs and recordings containing camera video,
the score graph and log text.
