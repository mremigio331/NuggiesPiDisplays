const path = require("path");
const HtmlWebpackPlugin = require("html-webpack-plugin");

module.exports = {
  entry: "./src/index.js",
  output: {
    path: path.resolve(__dirname, "dist"),
    filename: "bundle.[contenthash].js",
    publicPath: "/",
    clean: true,
  },
  module: {
    rules: [
      {
        test: /\.(js|jsx)$/,
        exclude: /node_modules/,
        use: "babel-loader",
      },
      {
        test: /\.css$/,
        use: ["style-loader", "css-loader"],
      },
      {
        test: /\.(svg|png|jpg|gif)$/,
        type: "asset/resource",
      },
    ],
  },
  plugins: [
    new HtmlWebpackPlugin({
      template: "./public/index.html",
      title: "Nuggies Display",
    }),
  ],
  devServer: {
    port: 8080,
    allowedHosts: "all",
    historyApiFallback: true,
    hot: true,
    liveReload: true,
    proxy: [{ context: ["/api"], target: "http://localhost:8000" }],
  },
};
