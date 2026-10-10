import React from 'react';
import { ScrollView, ScrollViewProps } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { C } from '../theme';

/** Scrolling page that clears the status bar. The tab bar sits below it in the layout, so nothing hides behind it. */
export default function Screen({ children, ...rest }: ScrollViewProps) {
  const { top } = useSafeAreaInsets();
  return (
    <ScrollView {...rest} style={[{ flex: 1, backgroundColor: C.bg }, rest.style]} keyboardShouldPersistTaps="handled"
      contentContainerStyle={[{ paddingTop: top + 16, paddingHorizontal: 20, paddingBottom: 28, gap: 16 }, rest.contentContainerStyle]}>
      {children}
    </ScrollView>
  );
}
