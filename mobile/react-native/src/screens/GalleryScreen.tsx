/**
 * 古玉鉴真 — 藏品图鉴浏览
 * FlatList 无限滚动 + 年代/真伪筛选 + 搜索; 离线时展示缓存快照
 */

import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { ERA_CODE, ERA_NAMES } from '../../../../shared/constants/eras';
import { useAppStore } from '../store/useAppStore';
import { imageUrl, serverClient, AnnotationRecord } from '../services/serverClient';
import { loadSnapshot, saveSnapshot } from '../cache/galleryCache';

const PAGE_SIZE = 30;

export function GalleryScreen({
  navigation,
}: {
  navigation: { navigate: (name: string, params: unknown) => void };
}): React.JSX.Element {
  const serverBase = useAppStore(s => s.serverBase);
  const [items, setItems] = useState<AnnotationRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [offline, setOffline] = useState<string>(''); // 缓存时间提示
  const [era, setEra] = useState<string>('');
  const [auth, setAuth] = useState<string>('');
  const [q, setQ] = useState('');

  const fetchPage = useCallback(
    async (offset: number, replace: boolean) => {
      setLoading(true);
      try {
        const res = await serverClient.listAnnotations(serverBase, {
          limit: PAGE_SIZE,
          offset,
          era_code: era || undefined,
          authenticity: auth || undefined,
          q: q || undefined,
        });
        setItems(prev => (replace ? res.data : [...prev, ...res.data]));
        setTotal(res.total);
        setOffline('');
        if (replace && offset === 0) {
          // 首屏快照缓存 (图鉴离线浏览)
          saveSnapshot({
            updatedAt: new Date().toISOString(),
            items: res.data,
            total: res.total,
          }).catch(() => {});
        }
      } catch {
        // 离线 → 展示缓存快照
        const snap = await loadSnapshot();
        if (snap) {
          setItems(snap.items);
          setTotal(snap.total);
          setOffline(snap.updatedAt);
        }
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [serverBase, era, auth, q],
  );

  useEffect(() => {
    fetchPage(0, true);
  }, [fetchPage]);

  const loadMore = () => {
    if (!loading && items.length < total) fetchPage(items.length, false);
  };

  const renderItem = ({ item }: { item: AnnotationRecord }) => (
    <Pressable
      style={styles.card}
      onPress={() => navigation.navigate('PieceDetail', { record: item })}>
      <Image
        source={{ uri: imageUrl(serverBase, item.image_paths?.[0] || item.training_image, 300) }}
        style={styles.thumb}
        onError={() => {}}
      />
      <View style={styles.cardInfo}>
        <View style={styles.cardTop}>
          <Text
            style={[
              styles.badge,
              item.authenticity === '真老' ? styles.badgeGenuine : styles.badgeFake,
            ]}>
            {item.authenticity}
          </Text>
          <Text style={styles.cardEra}>
            {item.era} ({item.era_code})
          </Text>
        </View>
        <Text style={styles.cardName} numberOfLines={1}>
          {item.product_name || '未命名'}
        </Text>
        <Text style={styles.cardSource} numberOfLines={1}>
          {(item.source_detail || '').slice(0, 24) || '—'}
        </Text>
      </View>
    </Pressable>
  );

  return (
    <View style={styles.page}>
      <Text style={styles.title}>📚 藏品图鉴</Text>
      {offline ? (
        <Text style={styles.offlineTip}>离线缓存 (同步于 {offline.slice(0, 16).replace('T', ' ')})</Text>
      ) : null}

      <View style={styles.filters}>
        <TextInput
          style={styles.search}
          placeholder="搜索品名/编号"
          placeholderTextColor="#6a5f4e"
          value={q}
          onChangeText={setQ}
          onSubmitEditing={() => fetchPage(0, true)}
        />
        <ScrollView horizontal showsHorizontalScrollIndicator={false}>
          {ERA_CODE.map(code => (
            <Pressable
              key={code}
              style={[styles.chip, era === code && styles.chipActive]}
              onPress={() => setEra(era === code ? '' : code)}>
              <Text
                style={[styles.chipText, era === code && styles.chipTextActive]}>
                {code} {ERA_NAMES[code]}
              </Text>
            </Pressable>
          ))}
        </ScrollView>
        <View style={styles.authRow}>
          {['', '真老', '新仿'].map(v => (
            <Pressable
              key={v || 'all'}
              style={[styles.chip, auth === v && styles.chipActive]}
              onPress={() => setAuth(v)}>
              <Text
                style={[styles.chipText, auth === v && styles.chipTextActive]}>
                {v || '全部'}
              </Text>
            </Pressable>
          ))}
        </View>
      </View>

      <Text style={styles.count}>共 {total} 条 · 已加载 {items.length}</Text>

      <FlatList
        data={items}
        keyExtractor={it => it.id}
        renderItem={renderItem}
        onEndReached={loadMore}
        onEndReachedThreshold={0.4}
        refreshing={refreshing}
        onRefresh={() => {
          setRefreshing(true);
          fetchPage(0, true);
        }}
        ListFooterComponent={loading ? <ActivityIndicator color="#8c6a3f" /> : null}
        contentContainerStyle={styles.list}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: '#141210', paddingTop: 16 },
  title: { color: '#e8d9b0', fontSize: 22, fontWeight: '700', paddingHorizontal: 20 },
  offlineTip: { color: '#c98f4e', fontSize: 12, paddingHorizontal: 20, marginTop: 4 },
  filters: { paddingHorizontal: 20, gap: 8, marginTop: 10 },
  search: {
    backgroundColor: '#1e1a16',
    borderColor: '#5a4f3e',
    borderWidth: 1,
    borderRadius: 8,
    color: '#e8d9b0',
    padding: 8,
    fontSize: 13,
  },
  chip: {
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#5a4f3e',
    marginRight: 6,
  },
  chipActive: { backgroundColor: '#8c6a3f', borderColor: '#8c6a3f' },
  chipText: { color: '#9a8d75', fontSize: 12 },
  chipTextActive: { color: '#fff', fontWeight: '600' },
  authRow: { flexDirection: 'row' },
  count: { color: '#6a5f4e', fontSize: 12, paddingHorizontal: 20, marginTop: 8 },
  list: { padding: 20, gap: 10 },
  card: {
    flexDirection: 'row',
    backgroundColor: '#1e1a16',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#3a322a',
    overflow: 'hidden',
    marginBottom: 10,
  },
  thumb: { width: 84, height: 84, backgroundColor: '#2a241e' },
  cardInfo: { flex: 1, padding: 8, gap: 3 },
  cardTop: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  badge: {
    fontSize: 11,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
    overflow: 'hidden',
  },
  badgeGenuine: { backgroundColor: '#2f4a2a', color: '#7fb069' },
  badgeFake: { backgroundColor: '#4a2a2a', color: '#e07a5f' },
  cardEra: { color: '#c9b98f', fontSize: 13 },
  cardName: { color: '#e8d9b0', fontSize: 14, fontWeight: '600' },
  cardSource: { color: '#6a5f4e', fontSize: 11 },
});
