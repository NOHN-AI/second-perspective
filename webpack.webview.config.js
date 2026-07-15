//@ts-check
const path = require('path');

/** VS Code webview bundle (React). Runs in the webview's browser context,
 *  so React is bundled (no node_modules access there) and vscode is NOT an external.
 * @type {import('webpack').Configuration}
 */
module.exports = {
  target: 'web',
  mode: 'none',
  entry: './src/ui/webview/index.tsx',
  output: {
    path: path.resolve(__dirname, 'dist'),
    filename: 'webview.js',
    publicPath: '',
  },
  resolve: {
    extensions: ['.ts', '.tsx', '.js'],
    fallback: { fs: false, path: false, crypto: false },
  },
  module: {
    rules: [
      { test: /\.tsx?$/, exclude: /node_modules/, use: [{ loader: 'ts-loader' }] },
      { test: /\.css$/, use: ['style-loader', 'css-loader'] },
    ],
  },
  performance: { hints: false },
  devtool: 'nosources-source-map',
};
