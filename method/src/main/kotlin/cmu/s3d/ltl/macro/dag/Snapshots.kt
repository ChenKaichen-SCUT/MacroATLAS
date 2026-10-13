package cmu.s3d.ltl.macro.dag

import java.util.Collections

internal fun <T> immutableList(values: Collection<T>): List<T> = Collections.unmodifiableList(ArrayList(values))
internal fun <T> immutableSet(values: Collection<T>): Set<T> = Collections.unmodifiableSet(LinkedHashSet(values))
internal fun <K, V> immutableMap(values: Map<K, V>): Map<K, V> = Collections.unmodifiableMap(LinkedHashMap(values))
