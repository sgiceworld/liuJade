/**
 * 古玉鉴真 — 藏品详情页 (原图 + 元数据)
 */

import React from 'react';
import { Dimensions, Image, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useAppStore } from '../store/useAppStore';
import { imageUrl, AnnotationRecord } from '../services/serverClient';

const W = Dimensions.get('window').width;

export function PieceDetailScreen({
  route,
}: {
  route: { params: { record: AnnotationRecord } };
}): React.JSX.Element {
  const serverBase = useAppStore(s => s.serverBase);
  const rec = route.params.record;
  const img = rec.image_paths?.[0] || rec.training_image;

  return (
    <ScrollView style={styles.page}>
      {img ? (
        <Image
          source={{ uri: imageUrl(serverBase, img) }}
          style={styles.image}
          resizeMode="contain"
        />
      ) : (
        <View style={styles.noImage}>
          <Text style={styles.noImageText}>无图片</Text>
        </View>
      )}

      <View style={styles.info}>
        <Text style={styles.name}>{rec.product_name || '未命名'}</Text>
        <Row label="标签编码" value={rec.label_code} />
        <Row label="年代" value={`${rec.era || ''} (${rec.era_code})`} />
        <Row label="真伪" value={rec.authenticity} />
        <Row label="材质" value={rec.material || '—'} />
        <Row label="来源" value={rec.source_type || '—'} />
        <Row label="来源详情" value={rec.source_detail || '—'} />
        <Row label="标注人" value={rec.annotated_by || '—'} />
        <Row label="置信度" value={String(rec.annotation_confidence ?? '—')} />
        <Row label="备注" value={rec.notes || '—'} />
      </View>
    </ScrollView>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.row}>
      <Text style={styles.rowLabel}>{label}</Text>
      <Text style={styles.rowValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: '#141210' },
  image: { width: W, height: W, backgroundColor: '#0d0b09' },
  noImage: { width: W, height: 200, alignItems: 'center', justifyContent: 'center' },
  noImageText: { color: '#6a5f4e' },
  info: { padding: 16, gap: 10 },
  name: { color: '#e8d9b0', fontSize: 20, fontWeight: '700' },
  row: { flexDirection: 'row', gap: 10 },
  rowLabel: { color: '#6a5f4e', fontSize: 13, width: 70 },
  rowValue: { color: '#c9b98f', fontSize: 13, flex: 1 },
});
