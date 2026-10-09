/**
 * 古玉鉴真 — 样品采集
 * 表单 + 多图 + AI 预填 (本地推理) + 在线提交 / 离线入队自动 flush
 */

import React, { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { launchImageLibrary } from 'react-native-image-picker';
import { MATERIALS } from '../../../../shared/constants/materials';
import { ERA_CODE, ERA_NAMES } from '../../../../shared/constants/eras';
import { useAppStore } from '../store/useAppStore';
import { serverClient, AnnotationSavePayload } from '../services/serverClient';
import { authenticateLocal } from '../localInference/engine';
import { modelStore } from '../localInference/modelStore';
import { enqueue, flushQueue, queueLength } from '../cache/collectQueue';

export function CollectScreen(): React.JSX.Element {
  const serverBase = useAppStore(s => s.serverBase);
  const [productName, setProductName] = useState('');
  const [material, setMaterial] = useState<string>(MATERIALS[0]);
  const [sourceDetail, setSourceDetail] = useState('');
  const [notes, setNotes] = useState('');
  const [eraCode, setEraCode] = useState<string>('');
  const [authenticity, setAuthenticity] = useState<'真老' | '新仿'>('真老');
  const [photoUris, setPhotoUris] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [prefilling, setPrefilling] = useState(false);
  const [message, setMessage] = useState('');
  const [pending, setPending] = useState(0);

  useEffect(() => {
    queueLength().then(setPending);
  }, []);

  const pickPhotos = () => {
    launchImageLibrary(
      { mediaType: 'photo', selectionLimit: 0, includeBase64: false },
      res => {
        if (res.didCancel) return;
        const uris = (res.assets || []).map(a => a.uri!).filter(Boolean);
        setPhotoUris(prev => [...prev, ...uris]);
      },
    );
  };

  /** 本地模型预填年代/真伪 (可改) */
  const aiPrefill = async () => {
    if (photoUris.length === 0 || !(await modelStore.isReady())) {
      setMessage(photoUris.length === 0 ? '请先选择照片' : '端侧模型未下载');
      return;
    }
    setPrefilling(true);
    setMessage('');
    try {
      const r = await authenticateLocal(photoUris[0], photoUris[0]);
      setEraCode(r.era_code);
      setAuthenticity(r.predicted_authenticity);
      setMessage(
        `AI 预填: ${r.predicted_era} / ${r.predicted_authenticity} (置信 ${(r.authenticity_confidence * 100).toFixed(0)}%)`,
      );
    } catch (e) {
      setMessage(`预填失败: ${(e as Error).message}`);
    } finally {
      setPrefilling(false);
    }
  };

  const buildPayload = (): AnnotationSavePayload => ({
    authenticity,
    era_code: eraCode || 'A',
    product_name: productName || '待命名',
    material,
    source_type: '采集',
    source_detail: sourceDetail || '移动端现场采集',
    annotated_by: '移动端',
    annotation_confidence: 1,
  });

  const submit = async () => {
    setBusy(true);
    setMessage('');
    try {
      const uploaded = await serverClient.uploadImages(
        serverBase,
        photoUris.map(uri => ({ uri, type: 'macro' as const })),
      );
      const saved = await serverClient.saveAnnotation(serverBase, {
        ...buildPayload(),
        image_paths: uploaded.map(u => u.path),
      });
      setMessage(`✓ 已提交: ${saved.label_code}`);
      setPhotoUris([]);
      setProductName('');
      setNotes('');
      setEraCode('');
    } catch {
      // 离线 → 入队, 恢复网络后自动 flush
      await enqueue(buildPayload(), photoUris);
      setPending(await queueLength());
      setMessage('📴 离线, 已入队, 联网后自动同步');
    } finally {
      setBusy(false);
    }
  };

  const flushNow = async () => {
    setBusy(true);
    const res = await flushQueue(serverBase);
    setPending(await queueLength());
    setMessage(`同步完成: ${res.ok} 成功 / ${res.failed} 失败`);
    setBusy(false);
  };

  return (
    <ScrollView style={styles.page} contentContainerStyle={styles.container}>
      <Text style={styles.title}>📝 样品采集</Text>
      <Text style={styles.subtitle}>现场采集样品 → 回传 PC 标注库 (source_type=采集)</Text>

      <Pressable style={styles.photoRow} onPress={pickPhotos}>
        {photoUris.map(uri => (
          <Image key={uri} source={{ uri }} style={styles.thumb} />
        ))}
        <View style={styles.addBox}>
          <Text style={styles.addText}>+ 选图</Text>
        </View>
      </Pressable>

      <TextInput
        style={styles.input}
        placeholder="品名 (如 新仿清式玉璧)"
        placeholderTextColor="#6a5f4e"
        value={productName}
        onChangeText={setProductName}
      />
      <Text style={styles.label}>材质</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false}>
        {MATERIALS.map(m => (
          <Pressable
            key={m}
            style={[styles.chip, material === m && styles.chipActive]}
            onPress={() => setMaterial(m)}>
            <Text style={[styles.chipText, material === m && styles.chipTextActive]}>
              {m}
            </Text>
          </Pressable>
        ))}
      </ScrollView>
      <Text style={styles.label}>年代 (AI 预填可改)</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false}>
        {ERA_CODE.map(code => (
          <Pressable
            key={code}
            style={[styles.chip, eraCode === code && styles.chipActive]}
            onPress={() => setEraCode(code)}>
            <Text style={[styles.chipText, eraCode === code && styles.chipTextActive]}>
              {code} {ERA_NAMES[code]}
            </Text>
          </Pressable>
        ))}
      </ScrollView>
      <Text style={styles.label}>真伪</Text>
      <View style={styles.authRow}>
        {(['真老', '新仿'] as const).map(v => (
          <Pressable
            key={v}
            style={[styles.chip, authenticity === v && styles.chipActive]}
            onPress={() => setAuthenticity(v)}>
            <Text style={[styles.chipText, authenticity === v && styles.chipTextActive]}>
              {v}
            </Text>
          </Pressable>
        ))}
      </View>
      <TextInput
        style={styles.input}
        placeholder="来源详情 (地点/渠道)"
        placeholderTextColor="#6a5f4e"
        value={sourceDetail}
        onChangeText={setSourceDetail}
      />
      <TextInput
        style={styles.input}
        placeholder="备注"
        placeholderTextColor="#6a5f4e"
        value={notes}
        onChangeText={setNotes}
        multiline
      />

      <View style={styles.btnRow}>
        <Pressable style={[styles.btn, styles.btnSecondary]} onPress={aiPrefill} disabled={prefilling}>
          {prefilling ? <ActivityIndicator color="#fff" /> : <Text style={styles.btnText}>🤖 AI 预填</Text>}
        </Pressable>
        <Pressable style={styles.btn} onPress={submit} disabled={busy}>
          {busy ? <ActivityIndicator color="#fff" /> : <Text style={styles.btnText}>提交</Text>}
        </Pressable>
      </View>
      {pending > 0 && (
        <Pressable style={[styles.btn, styles.btnSecondary]} onPress={flushNow}>
          <Text style={styles.btnText}>📤 同步离线队列 ({pending})</Text>
        </Pressable>
      )}
      {message ? <Text style={styles.message}>{message}</Text> : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: '#141210' },
  container: { padding: 20, gap: 12 },
  title: { color: '#e8d9b0', fontSize: 22, fontWeight: '700' },
  subtitle: { color: '#9a8d75', fontSize: 13 },
  photoRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  thumb: { width: 72, height: 72, borderRadius: 8, backgroundColor: '#2a241e' },
  addBox: {
    width: 72,
    height: 72,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#5a4f3e',
    alignItems: 'center',
    justifyContent: 'center',
  },
  addText: { color: '#8a7d65', fontSize: 12 },
  input: {
    backgroundColor: '#1e1a16',
    borderColor: '#5a4f3e',
    borderWidth: 1,
    borderRadius: 8,
    color: '#e8d9b0',
    padding: 10,
    fontSize: 14,
  },
  label: { color: '#c9b98f', fontSize: 13, marginTop: 4 },
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
  btnRow: { flexDirection: 'row', gap: 10 },
  btn: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 10,
    backgroundColor: '#8c6a3f',
    alignItems: 'center',
  },
  btnSecondary: { backgroundColor: '#3a322a' },
  btnText: { color: '#fff', fontSize: 15, fontWeight: '600' },
  message: { color: '#b5a888', fontSize: 13, textAlign: 'center' },
});
