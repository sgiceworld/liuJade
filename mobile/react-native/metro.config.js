const {getDefaultConfig, mergeConfig} = require('@react-native/metro-config');
const path = require('path');

/**
 * Metro 单仓配置:
 * - watchFolders 指向仓库根, 使 ../../shared 可被 watch/import (相对路径)
 * - assetExts 加 'onnx' (备选: 模型打包进 APK assets)
 *
 * @type {import('@react-native/metro-config').MetroConfig}
 */
const config = {
  watchFolders: [path.resolve(__dirname, '../..')],
  resolver: {
    assetExts: [...getDefaultConfig(__dirname).resolver.assetExts, 'onnx'],
  },
};

module.exports = mergeConfig(getDefaultConfig(__dirname), config);
