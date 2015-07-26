clean:
	find . | grep -E '(__pycache__|\.py[oc])' | xargs rm -rf
