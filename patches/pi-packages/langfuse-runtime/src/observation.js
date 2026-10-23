async function startChildObservation({
  parent,
  runtime,
  name,
  body,
  asType
}) {
  if (parent.startObservation) {
    return parent.startObservation(name, body, { asType });
  }
  return (await runtime()).startObservation(name, body, { asType });
}
export {
  startChildObservation
};
